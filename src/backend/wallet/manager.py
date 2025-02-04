class WalletManager:
    def __init__(self):
        self.hot_wallet = HotWallet()  # 热钱包（小额交易）
        self.cold_wallet = ColdWallet()  # 冷钱包（大额存储）
