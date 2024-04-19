def generateWalletNumber(member_id):
    prefix = "94" + str(member_id)
    wallet_number = prefix.zfill(12)
    return wallet_number
