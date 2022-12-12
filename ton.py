import asyncio
import json

import requests

from ton_utils import *
from values import *


async def get_ton_addresses(address):
    addresses = detect_address(address)
    return {'b64': addresses['bounceable']['b64'],
            'b64url': addresses['bounceable']['b64url'],
            'n_b64': addresses['non_bounceable']['b64'],
            'n_b64url': addresses['non_bounceable']['b64url'],
            'raw': addresses['raw_form']}


async def get_user_nfts(address):
    address = (await get_ton_addresses(address))['b64url']
    await asyncio.sleep(1)
    all_nfts = json.loads(requests.get(f"https://tonapi.io/v1/nft/searchItems",
                                       params={"owner": address,
                                               "collection": COLLECTION,
                                               "include_on_sale": "true",
                                               "limit": "50",
                                               "offset": 0}).text)['nft_items']
    nfts = []
    for nft in all_nfts:
        try:
            name = nft['metadata']['name']
            address = (await get_ton_addresses(nft['address']))['b64url']
            image = nft['metadata']['image']
            nfts += [{'address': address, 'name': name, 'image': image}]
        except:
            pass
    print(nfts)
    return nfts
