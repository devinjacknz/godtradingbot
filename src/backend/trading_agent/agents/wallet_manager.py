"""Mock wallet manager module for testing"""
import base58


class WalletManager:
    def __init__(self):
        self._balance = 10.0  # Mock balance for testing
        self._public_key = base58.b58encode(b"mock_public_key").decode()
        self._private_key = base58.b58encode(b"mock_private_key").decode()

    async def get_balance(self) -> float:
        """Get wallet balance"""
        return self._balance

    def get_public_key(self) -> str:
        """Get wallet public key"""
        return self._public_key

    def get_private_key(self) -> str:
        """Get wallet private key"""
        return self._private_key

    async def send_transaction(self, to_address: str, amount: float) -> str:
        """Send transaction

        Args:
            to_address: Destination address
            amount: Amount to send

        Returns:
            Transaction hash
        """
        if amount > self._balance:
            raise ValueError("Insufficient funds")

        self._balance -= amount
        return base58.b58encode(b"mock_tx_hash").decode()

    async def sign_message(self, message: bytes) -> bytes:
        """Sign message with private key

        Args:
            message: Message to sign

        Returns:
            Signature
        """
        return base58.b58encode(b"mock_signature")
