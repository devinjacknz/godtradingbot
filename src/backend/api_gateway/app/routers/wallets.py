import logging
import secrets
from typing import List, Optional

import base58
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class WalletCreate(BaseModel):
    bot_id: str


class WalletResponse(BaseModel):
    address: str
    private_key: str
    bot_id: str
    balance: float = 0.0


class WalletListResponse(BaseModel):
    wallets: List[WalletResponse]


wallets_db = {}


def generate_mock_solana_keypair():
    private_key = secrets.token_bytes(32)
    address = base58.b58encode(secrets.token_bytes(32)).decode("utf-8")
    return private_key.hex(), address


@router.post("/wallets", response_model=WalletResponse)
async def create_wallet(wallet_request: WalletCreate):
    try:
        private_key, address = generate_mock_solana_keypair()
        wallet = WalletResponse(
            address=address,
            private_key=private_key,
            bot_id=wallet_request.bot_id,
            balance=0.5,  # Initial balance for testing
        )
        wallets_db[address] = wallet
        logger.info(f"Created wallet for bot {wallet_request.bot_id}")
        return wallet
    except Exception as e:
        logger.error(f"Failed to create wallet: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create wallet")


@router.get("/wallets", response_model=WalletListResponse)
async def list_wallets():
    try:
        return WalletListResponse(wallets=list(wallets_db.values()))
    except Exception as e:
        logger.error(f"Failed to list wallets: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list wallets")


@router.get("/wallets/{bot_id}", response_model=WalletResponse)
async def get_wallet(bot_id: str):
    try:
        wallet = next((w for w in wallets_db.values() if w.bot_id == bot_id), None)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        return wallet
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get wallet for bot {bot_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get wallet")
