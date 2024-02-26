import stripe
import grannymail.config as cfg

stripe.api_key = cfg.STRIPE_API_KEY
# client = stripe.StripeClient(cfg.STRIPE_API_KEY)


def get_credits_bought(payment_link_id: str) -> int:
    items_bought = stripe.PaymentLink.list_line_items(payment_link_id)["data"]
    total_credits = 0
    for item in items_bought:
        product_id = item["price"]["product"]
        product = stripe.Product.retrieve(product_id)
        letter_credits = product["metadata"]["letter_credits"]
        total_credits += int(letter_credits)
    return total_credits


if __name__ == "__main__":
    plink = "plink_1Oo9zHLuDIWxSZxaQAbFlPrQ"
    print(get_credits_bought(plink))
