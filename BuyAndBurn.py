#!/usr/bin/env python3

import argparse
import json

from auctions.AuctionEngine import AuctionEngine
from auctions.BidUpToMaxRateStrategy import BidUpToMaxRateStrategy
from auctions.HandleExpiredAuctionletsStrategy import HandleExpiredAuctionletsStrategy
from auctions.IgnoreWinningAuctionletsStrategy import IgnoreWinningAuctionletsStrategy
from auctions.OnlyOneTokenPairPairStrategy import OnlyOneTokenPairPairStrategy
from contracts.Address import Address
from contracts.DSToken import DSToken
from contracts.ERC20Token import ERC20Token
from contracts.Wad import Wad
from contracts.auctions.AuctionManager import AuctionManager

from web3 import HTTPProvider
from web3 import Web3

parser = argparse.ArgumentParser(description='Maker BuyAndBurn keeper. Continuously trades MKR for DAI.')
parser.add_argument("--rpc-host", help="JSON-RPC host (default: `localhost')", default="localhost", type=str)
parser.add_argument("--rpc-port", help="JSON-RPC port (default: `8545')", default=8545, type=int)
parser.add_argument("--number-of-recent-blocks", help="Number of previous blocks to scan looking for active auctions (default: 10000)", default=10000, type=int)
parser.add_argument("--frequency", help="Frequency of periodical checking of existing auctions (in seconds) (default: 60)", default=60, type=int)
parser.add_argument("--auction-manager", help="Ethereum address of the AuctionManager to trade on", required=True, type=str)
parser.add_argument("--trader", help="Ethereum address of the trader ie. the account that owns MKR will receive DAI", required=True, type=str)
parser.add_argument("--mkr-token", help="Ethereum address of the MKR ERC20 token contract", required=True, type=str)
parser.add_argument("--dai-token", help="Ethereum address of the DAI ERC20 token contract", required=True, type=str)
parser.add_argument("--max-price", help="Maximum number of MKR you are willing to pay for one DAI", required=True, type=float)
parser.add_argument("--minimal-bid", help="Minimal amount of MKR you want to bid", required=True, type=float)
parser.add_argument("--step", help="Incremental step towards the maximum price (value between 0 and 1)", required=True, type=float)
args = parser.parse_args()

with open('addresses.json') as data_file:
    network = "kovan"
    addresses = json.load(data_file)

web3 = Web3(HTTPProvider(endpoint_uri=f"http://{args.rpc_host}:{args.rpc_port}"))
web3.eth.defaultAccount = args.trader

auction_manager_address = Address(args.auction_manager)
auction_manager = AuctionManager(web3=web3, address=auction_manager_address, is_splitting=True)
trader_address = Address(args.trader)
dai_address = Address(addresses[network]["DAI"])
dai_token = ERC20Token(web3=web3, address=dai_address)
mkr_address = Address(addresses[network]["MKR"])
mkr_token = DSToken(web3=web3, address=mkr_address)

for key, value in addresses[network].items():
    ERC20Token.register_token(Address(value), key)

strategy = BidUpToMaxRateStrategy(args.max_price, args.step, Wad(args.minimal_bid*1000000000000000000))
strategy = IgnoreWinningAuctionletsStrategy(strategy)
strategy = HandleExpiredAuctionletsStrategy(strategy)
strategy = OnlyOneTokenPairPairStrategy(dai_token, mkr_token, strategy)

engine = AuctionEngine(auction_manager, trader_address, strategy, args.frequency, args.number_of_recent_blocks)
engine.start()
