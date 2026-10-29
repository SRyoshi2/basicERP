from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP


MONEY_QUANTUM = Decimal("0.01")
HUNDRED = Decimal("100")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def line_net(quantity: Decimal, unit_price_net: Decimal, discount_percent: Decimal) -> Decimal:
    discount_factor = (HUNDRED - discount_percent) / HUNDRED
    return money(quantity * unit_price_net * discount_factor)


def calculate_document(lines) -> dict:
    net_by_rate = defaultdict(lambda: Decimal("0.00"))
    for line in lines:
        net_by_rate[line.tax_rate] += line_net(
            line.quantity, line.unit_price_net, line.discount_percent
        )

    breakdown = []
    net_total = Decimal("0.00")
    tax_total = Decimal("0.00")
    for tax_rate in sorted(net_by_rate):
        net_amount = money(net_by_rate[tax_rate])
        tax_amount = money(net_amount * tax_rate / HUNDRED)
        breakdown.append({
            "tax_rate": money(tax_rate),
            "net_amount": net_amount,
            "tax_amount": tax_amount,
            "gross_amount": net_amount + tax_amount,
        })
        net_total += net_amount
        tax_total += tax_amount

    return {
        "net_total": money(net_total),
        "tax_total": money(tax_total),
        "gross_total": money(net_total + tax_total),
        "tax_breakdown": breakdown,
    }
