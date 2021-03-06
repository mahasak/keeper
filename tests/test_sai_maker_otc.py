# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017 reverendus
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import py

from keeper import Wad
from keeper.api.feed import DSValue
from keeper.api.token import DSToken, ERC20Token
from keeper.sai_maker_otc import SaiMakerOtc
from tests.conftest import SaiDeployment
from tests.helper import args


class TestSaiMakerOtc:
    @staticmethod
    def write_sample_config(tmpdir):
        file = tmpdir.join("config.json")
        file.write("""{
            "buyBands": [
                {
                    "minMargin": 0.02,
                    "avgMargin": 0.04,
                    "maxMargin": 0.06,
                    "minSaiAmount": 50.0,
                    "avgSaiAmount": 75.0,
                    "maxSaiAmount": 100.0,
                    "dustCutoff": 0.0
                }
            ],
            "sellBands": [
                {
                    "minMargin": 0.02,
                    "avgMargin": 0.04,
                    "maxMargin": 0.06,
                    "minWEthAmount": 5.0,
                    "avgWEthAmount": 7.5,
                    "maxWEthAmount": 10.0,
                    "dustCutoff": 0.0
                }
            ]
        }""")
        return file

    @staticmethod
    def mint_tokens(sai: SaiDeployment):
        DSToken(web3=sai.web3, address=sai.tub.gem()).mint(Wad.from_number(1000)).transact()
        DSToken(web3=sai.web3, address=sai.tub.sai()).mint(Wad.from_number(1000)).transact()

    @staticmethod
    def set_price(sai: SaiDeployment, price: Wad):
        DSValue(web3=sai.web3, address=sai.tub.pip()).poke_with_int(price.value).transact()

    @staticmethod
    def offers_by_token(sai: SaiDeployment, token: ERC20Token):
        return list(filter(lambda offer: offer.sell_which_token == token.address, sai.otc.active_offers()))

    def test_should_create_offers_on_startup(self, sai: SaiDeployment, tmpdir: py.path.local):
        # given
        config_file = self.write_sample_config(tmpdir)

        # and
        keeper = SaiMakerOtc(args=args(f"--eth-from {sai.web3.eth.defaultAccount} --config {config_file}"),
                             web3=sai.web3, config=sai.get_config())

        # and
        self.mint_tokens(sai)
        self.set_price(sai, Wad.from_number(250))

        # when
        keeper.approve()
        keeper.synchronize_offers()

        # then
        assert len(sai.otc.active_offers()) == 2

        # and
        assert self.offers_by_token(sai, sai.sai)[0].owner == sai.our_address
        assert self.offers_by_token(sai, sai.sai)[0].sell_how_much == Wad.from_number(75)
        assert self.offers_by_token(sai, sai.sai)[0].sell_which_token == sai.sai.address
        assert self.offers_by_token(sai, sai.sai)[0].buy_how_much == Wad.from_number(0.3125)
        assert self.offers_by_token(sai, sai.sai)[0].buy_which_token == sai.gem.address

        # and
        assert self.offers_by_token(sai, sai.gem)[0].owner == sai.our_address
        assert self.offers_by_token(sai, sai.gem)[0].sell_how_much == Wad.from_number(7.5)
        assert self.offers_by_token(sai, sai.gem)[0].sell_which_token == sai.gem.address
        assert self.offers_by_token(sai, sai.gem)[0].buy_how_much == Wad.from_number(1950)
        assert self.offers_by_token(sai, sai.gem)[0].buy_which_token == sai.sai.address

    def test_should_cancel_offers_on_shutdown(self, sai: SaiDeployment, tmpdir: py.path.local):
        # given
        config_file = self.write_sample_config(tmpdir)

        # and
        keeper = SaiMakerOtc(args=args(f"--eth-from {sai.web3.eth.defaultAccount} --config {config_file}"),
                             web3=sai.web3, config=sai.get_config())

        # and
        self.mint_tokens(sai)
        self.set_price(sai, Wad.from_number(250))

        # and
        keeper.approve()
        keeper.synchronize_offers()
        assert len(sai.otc.active_offers()) == 2

        # when
        keeper.shutdown()

        # then
        assert len(sai.otc.active_offers()) == 0

    def test_should_place_extra_offer_only_if_offer_brought_below_min(self, sai: SaiDeployment, tmpdir: py.path.local):
        # given
        config_file = self.write_sample_config(tmpdir)

        # and
        keeper = SaiMakerOtc(args=args(f"--eth-from {sai.web3.eth.defaultAccount} --config {config_file}"),
                             web3=sai.web3, config=sai.get_config())

        # and
        self.mint_tokens(sai)
        self.set_price(sai, Wad.from_number(250))

        # and
        keeper.approve()
        keeper.synchronize_offers()
        assert len(sai.otc.active_offers()) == 2
        sai_offer_id = self.offers_by_token(sai, sai.sai)[0].offer_id

        # when
        sai.otc.take(sai_offer_id, Wad.from_number(20)).transact()
        # and
        keeper.synchronize_offers()
        # then
        assert len(sai.otc.active_offers()) == 2

        # when
        sai.otc.take(sai_offer_id, Wad.from_number(5)).transact()
        # and
        keeper.synchronize_offers()
        # then
        assert len(sai.otc.active_offers()) == 2

        # when
        sai.otc.take(sai_offer_id, Wad.from_number(1)).transact()
        # and
        keeper.synchronize_offers()
        # then
        assert len(sai.otc.active_offers()) == 3
        assert sai.otc.active_offers()[2].sell_how_much == Wad.from_number(26)
        assert sai.otc.active_offers()[2].sell_which_token == sai.sai.address
        assert sai.otc.active_offers()[2].buy_how_much == Wad(108333333333333333)
        assert sai.otc.active_offers()[2].buy_which_token == sai.gem.address
