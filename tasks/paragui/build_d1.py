"""D1 - Larder & Co web shop: one repo + one running dev server (port 8111) + VS Code + Chrome.

A (pgd1cart): fix the cart-total bug from ISSUE-42 (the customer's cart exists only as a screenshot), regression test,
             restart the server, update the issue, commit.
B (pgd1export): bookkeeping CSV export whose layout is given only as a spreadsheet screenshot, link on the Orders page,
             README, test, restart, download the October file through Chrome, commit.
"""
import datetime as dt
import json
import os
import random
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_devrepo import dev_sh, font, make_repo  # noqa: E402

PORT = 8111
MARA = ("Mara Lindqvist", "mara@larder-co.example")
TOBIAS = ("Tobias Kern", "tobias.kern@kern-webdev.example")
HANNA = ("Hanna Vogt", "hanna@larder-co.example")

# sku, name, unit, price (cents, VAT incl.), autumn-sale percent, category
PRODUCTS = [
    ("OIL-500", "Cold-pressed olive oil", "500 ml", 1050, 20, "Pantry"),
    ("FLR-1K", "Sourdough rye flour", "1 kg", 320, 0, "Baking"),
    ("PAP-75", "Smoked paprika", "75 g", 415, 15, "Spices"),
    ("ANC-120", "Anchovies in olive oil", "120 g", 590, 0, "Pantry"),
    ("HON-250", "Heather honey", "250 g", 875, 10, "Pantry"),
    ("VIN-250", "Aged balsamic vinegar", "250 ml", 1290, 25, "Pantry"),
    ("TEA-100", "Darjeeling first flush", "100 g", 1150, 0, "Tea & coffee"),
    ("CHO-100", "Dark chocolate 85%", "100 g", 349, 0, "Sweets"),
    ("PAS-500", "Bronze-cut spaghetti", "500 g", 295, 0, "Pantry"),
    ("SAL-250", "Flaky sea salt", "250 g", 690, 0, "Spices"),
    ("CAP-90", "Salted capers", "90 g", 380, 30, "Pantry"),
    ("COF-250", "Espresso beans", "250 g", 990, 10, "Tea & coffee"),
]
CUSTOMER_CART = [("OIL-500", 3), ("PAP-75", 4), ("FLR-1K", 2), ("VIN-250", 1)]
FREE_FROM, SHIPPING = 3900, 490


def rhu(num, den):
    return (2 * num + den) // (2 * den)


def sale_price(price, pct):
    return rhu(price * (100 - pct), 100)


def price_cart(items, buggy=False):
    by = {p[0]: p for p in PRODUCTS}
    lines = []
    for sku, qty in items:
        _, name, unit, price, pct, _ = by[sku]
        if buggy:
            total = price * qty - round(price * pct / 100)
        else:
            total = sale_price(price, pct) * qty
        lines.append((sku, name, unit, price, pct, qty, total))
    sub = sum(x[-1] for x in lines)
    ship = 0 if not lines or sub >= FREE_FROM else SHIPPING
    return lines, sub, ship, sub + ship


def euro(c):
    return f"\u20ac{c // 100}.{c % 100:02d}"


# ------------------------------------------------------------------ repo sources
def catalog_py(sale=True):
    rows = "\n".join(f"    {{'sku': {s!r}, 'name': {n!r}, 'unit': {u!r}, 'price': {p}, 'sale_pct': {pc if sale else 0}, "
                     f"'category': {c!r}}}," for s, n, u, p, pc, c in PRODUCTS)
    return f'''"""Product catalogue. Prices are in euro cents and include VAT."""

PRODUCTS = [
{rows}
]

BY_SKU = {{p['sku']: p for p in PRODUCTS}}


def round_half_up(num, den):
    """num / den rounded to the nearest integer, halves rounded up (non-negative integers only)."""
    return (2 * num + den) // (2 * den)


def sale_price(product):
    """Unit price after the product's sale discount, rounded to the cent (this is what product pages show)."""
    return round_half_up(product['price'] * (100 - product.get('sale_pct', 0)), 100)


def euro(cents):
    return '\\u20ac%d.%02d' % (cents // 100, cents % 100)
'''


CART_PY = '''"""Cart pricing. See docs/PRICING.md for the rules."""
from dataclasses import dataclass, field

from .catalog import BY_SKU, sale_price

SHIPPING = 490            # flat shipping fee in cents
FREE_SHIPPING_FROM = 3900  # free shipping from this subtotal (cents)


@dataclass
class Line:
    sku: str
    name: str
    unit: str
    price: int        # regular unit price
    unit_price: int   # unit price after the sale discount
    qty: int
    total: int


@dataclass
class CartTotals:
    lines: list = field(default_factory=list)
    subtotal: int = 0
    shipping: int = 0
    total: int = 0


def line_total(product, qty):
    """Price of one cart line in cents, sale discount included."""
    price = product['price']
    discount = round(price * product.get('sale_pct', 0) / 100)
    return price * qty - discount


def price_cart(items):
    """items: iterable of (sku, qty). Returns CartTotals with all amounts in cents."""
    lines = []
    for sku, qty in items:
        p = BY_SKU[sku]
        lines.append(Line(sku, p['name'], p['unit'], p['price'], sale_price(p), qty, line_total(p, qty)))
    subtotal = sum(line.total for line in lines)
    shipping = 0 if not lines or subtotal >= FREE_SHIPPING_FROM else SHIPPING
    return CartTotals(lines, subtotal, shipping, subtotal + shipping)
'''

ORDERS_PY = '''"""Order storage: a JSON file in data/ (created from data/orders.seed.json on first use)."""
import datetime
import json
import os
import shutil
import threading

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
ORDERS = os.path.join(DATA, 'orders.json')
SEED = os.path.join(DATA, 'orders.seed.json')
PAYMENTS = ('PayPal', 'Card', 'Invoice')
_lock = threading.Lock()


def load_orders(path=None):
    """All orders, oldest first. Each order: id, created (YYYY-MM-DDTHH:MM, shop time), customer, email,
    items [{sku, qty, unit}], shipping, total (cents), payment, status ('paid' | 'cancelled' | 'refunded')."""
    path = path or ORDERS
    if path == ORDERS and not os.path.exists(path):
        shutil.copy(SEED, path)
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def add_order(customer, email, payment, totals, path=None, now=None):
    path = path or ORDERS
    with _lock:
        orders = load_orders(path)
        order = {
            'id': max([o['id'] for o in orders] or [1000]) + 1,
            'created': (now or datetime.datetime.now()).strftime('%Y-%m-%dT%H:%M'),
            'customer': customer, 'email': email,
            'items': [{'sku': l.sku, 'qty': l.qty, 'unit': l.unit_price} for l in totals.lines],
            'shipping': totals.shipping, 'total': totals.total, 'payment': payment, 'status': 'paid',
        }
        orders.append(order)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(orders, f, indent=1, ensure_ascii=False)
        os.replace(tmp, path)
        return order


def month_label(month):
    return datetime.date(int(month[:4]), int(month[5:7]), 1).strftime('%B %Y')
'''

VIEWS_PY = '''"""HTML pages (server-side rendered)."""
from html import escape

from .catalog import euro, sale_price
from .orders import month_label

NAV = [('/', 'Shop'), ('/cart', 'Cart'), ('/orders', 'Orders (admin)')]


def layout(title, body, active='/', cart_count=0):
    nav = ''.join(
        f'<a href="{href}" class="{"on" if href == active else ""}">{label}'
        + (f' <span class="badge">{cart_count}</span>' if href == '/cart' and cart_count else '') + '</a>'
        for href, label in NAV)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{escape(title)} \\u00b7 Larder &amp; Co</title>
<link rel="stylesheet" href="/static/style.css"></head>
<body><header><div class="wrap"><a class="logo" href="/">Larder &amp; Co</a><nav>{nav}</nav></div></header>
<main class="wrap">{body}</main>
<footer class="wrap">Larder &amp; Co Feinkost \\u00b7 Hamburg \\u00b7 development server</footer></body></html>"""


def price_html(p):
    if p.get('sale_pct'):
        return (f'<s>{euro(p["price"])}</s> <strong class="sale">{euro(sale_price(p))}</strong> '
                f'<span class="tag">-{p["sale_pct"]}%</span>')
    return f'<strong>{euro(p["price"])}</strong>'


def add_form(p):
    return (f'<form method="post" action="/cart/add" class="add"><input type="hidden" name="sku" value="{p["sku"]}">'
            f'<input type="number" name="qty" value="1" min="1" max="99"><button>Add to cart</button></form>')


def catalog_page(products, cart_count):
    cards = ''.join(
        f'<div class="card"><div class="cat">{escape(p["category"])}</div>'
        f'<h3><a href="/product/{p["sku"]}">{escape(p["name"])}</a></h3><div class="unit">{p["unit"]} \\u00b7 {p["sku"]}</div>'
        f'<div class="price">{price_html(p)}</div>{add_form(p)}</div>' for p in products)
    return layout('Shop', f'<h1>Autumn in the larder</h1><p class="lead">Small-batch pantry staples, '
                          f'shipped from Hamburg. Free shipping from \\u20ac39.</p><div class="grid">{cards}</div>',
                  '/', cart_count)


def product_page(p, cart_count):
    return layout(p['name'], f'<p><a href="/">\\u2190 back to the shop</a></p><h1>{escape(p["name"])}</h1>'
                             f'<p class="unit">{p["unit"]} \\u00b7 article {p["sku"]}</p>'
                             f'<p class="price big">{price_html(p)}</p>{add_form(p)}', '/', cart_count)


def cart_page(totals, cart_count):
    if not totals.lines:
        return layout('Cart', '<h1>Your cart</h1><p>Your cart is empty. <a href="/">Continue shopping</a></p>',
                      '/cart', cart_count)
    rows = ''
    for l in totals.lines:
        unit = (f'<s>{euro(l.price)}</s> {euro(l.unit_price)}' if l.unit_price != l.price else euro(l.price))
        rows += (f'<tr><td>{escape(l.name)} <span class="unit">{l.unit}</span></td><td class="num">{unit}</td>'
                 f'<td class="num">{l.qty}</td><td class="num line-total">{euro(l.total)}</td>'
                 f'<td><form method="post" action="/cart/remove"><input type="hidden" name="sku" value="{l.sku}">'
                 f'<button class="link">remove</button></form></td></tr>')
    ship = 'free' if totals.shipping == 0 else euro(totals.shipping)
    body = f"""<h1>Your cart</h1>
<table class="cart"><thead><tr><th>Product</th><th class="num">Price</th><th class="num">Qty</th><th class="num">Total</th><th></th></tr></thead>
<tbody>{rows}</tbody>
<tfoot><tr><td colspan="3">Subtotal</td><td class="num" id="cart-subtotal">{euro(totals.subtotal)}</td><td></td></tr>
<tr><td colspan="3">Shipping</td><td class="num" id="cart-shipping">{ship}</td><td></td></tr>
<tr class="grand"><td colspan="3">Total</td><td class="num" id="cart-total">{euro(totals.total)}</td><td></td></tr></tfoot></table>
<form method="post" action="/cart/clear"><button class="link">Empty cart</button></form>
<h2>Checkout</h2>
<form method="post" action="/checkout" class="checkout">
<label>Name <input name="name" required></label><label>E-mail <input name="email" type="email" required></label>
<label>Payment <select name="payment"><option>PayPal</option><option>Card</option><option>Invoice</option></select></label>
<button>Place order</button></form>"""
    return layout('Cart', body, '/cart', cart_count)


def confirmation_page(order):
    return layout('Thank you', f'<h1>Thank you!</h1><p>Order <strong>LC-{order["id"]}</strong> was placed: '
                               f'{euro(order["total"])} via {escape(order["payment"])}.</p><p><a href="/">Back to the shop</a></p>')


def orders_page(orders, month):
    months = sorted({o['created'][:7] for o in orders})
    month = month if month in months else (months[-1] if months else '')
    shown = [o for o in orders if o['created'][:7] == month]
    tabs = ''.join(f'<a href="/orders?month={m}" class="{"on" if m == month else ""}">{month_label(m)}</a>' for m in months)
    rows = ''.join(
        f'<tr class="{o["status"]}"><td><a href="/orders/{o["id"]}">LC-{o["id"]}</a></td>'
        f'<td>{o["created"].replace("T", " ")}</td><td>{escape(o["customer"])}</td>'
        f'<td class="num">{sum(i["qty"] for i in o["items"])}</td><td class="num">{euro(o["shipping"])}</td>'
        f'<td class="num">{euro(o["total"])}</td><td>{o["payment"]}</td><td>{o["status"]}</td></tr>' for o in shown)
    paid = sum(o['total'] for o in shown if o['status'] == 'paid')
    body = f"""<h1>Orders \\u2013 {month_label(month) if month else ''}</h1>
<div class="tabs">{tabs}</div>
<div class="actions"><button onclick="window.print()">Print</button></div>
<table class="orders"><thead><tr><th>Order</th><th>Date</th><th>Customer</th><th class="num">Items</th>
<th class="num">Shipping</th><th class="num">Total</th><th>Payment</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="muted">{len(shown)} orders \\u00b7 paid revenue {euro(paid)}</p>"""
    return layout('Orders', body, '/orders')


def order_page(o):
    items = ''.join(f'<li>{i["qty"]} \\u00d7 {i["sku"]} at {euro(i["unit"])}</li>' for i in o['items'])
    return layout(f'LC-{o["id"]}', f'<p><a href="/orders?month={o["created"][:7]}">\\u2190 Orders</a></p>'
                                  f'<h1>Order LC-{o["id"]}</h1><p>{o["created"].replace("T", " ")} \\u00b7 '
                                  f'{escape(o["customer"])} &lt;{escape(o["email"])}&gt;</p><ul>{items}</ul>'
                                  f'<p>Shipping {euro(o["shipping"])} \\u00b7 <strong>Total {euro(o["total"])}</strong> '
                                  f'\\u00b7 {o["payment"]} \\u00b7 {o["status"]}</p>', '/orders')


def not_found():
    return layout('Not found', '<h1>Not found</h1><p><a href="/">Back to the shop</a></p>')
'''

SERVER_PY = '''"""Larder & Co web shop - development server (Python stdlib only).

    python3 -m shop.server --port 8111      (or ./dev.sh start|stop|restart)

Carts live in memory (one per browser session cookie), so restarting the server empties them.
"""
import argparse
import os
import secrets
import sys
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import views
from .cart import price_cart
from .catalog import BY_SKU, PRODUCTS
from .orders import PAYMENTS, add_order, load_orders

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
CARTS = {}


class Handler(BaseHTTPRequestHandler):
    server_version = 'LarderDev/0.4'

    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\\n' % (self.log_date_time_string(), fmt % args))

    # -- helpers
    def session(self):
        jar = cookies.SimpleCookie(self.headers.get('Cookie', ''))
        sid = jar['larder_session'].value if 'larder_session' in jar else None
        if not sid or sid not in CARTS:
            sid = sid or secrets.token_hex(8)
            CARTS.setdefault(sid, {})
        self.sid = sid
        return CARTS[sid]

    def send(self, status, body, ctype='text/html; charset=utf-8', headers=None):
        data = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        if getattr(self, 'sid', None):
            self.send_header('Set-Cookie', 'larder_session=%s; Path=/; HttpOnly' % self.sid)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location):
        self.send(303, '', headers={'Location': location})

    def form(self):
        n = int(self.headers.get('Content-Length') or 0)
        return {k: v[0] for k, v in urllib.parse.parse_qs(self.rfile.read(n).decode('utf-8')).items()}

    # -- routes
    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        path, query = url.path, urllib.parse.parse_qs(url.query)
        cart = self.session()
        count = sum(cart.values())
        if path == '/':
            return self.send(200, views.catalog_page(PRODUCTS, count))
        if path.startswith('/product/') and path[9:] in BY_SKU:
            return self.send(200, views.product_page(BY_SKU[path[9:]], count))
        if path == '/cart':
            return self.send(200, views.cart_page(price_cart(list(cart.items())), count))
        if path == '/orders':
            return self.send(200, views.orders_page(load_orders(), query.get('month', [''])[0]))
        if path.startswith('/orders/') and path[8:].isdigit():
            order = next((o for o in load_orders() if o['id'] == int(path[8:])), None)
            if order:
                return self.send(200, views.order_page(order))
        if path == '/static/style.css':
            with open(os.path.join(STATIC, 'style.css'), 'rb') as f:
                return self.send(200, f.read(), 'text/css')
        return self.send(404, views.not_found())

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        cart = self.session()
        data = self.form()
        if path == '/cart/add':
            sku = data.get('sku', '')
            try:
                qty = max(1, min(99, int(data.get('qty', '1'))))
            except ValueError:
                qty = 1
            if sku in BY_SKU:
                cart[sku] = min(99, cart.get(sku, 0) + qty)
            return self.redirect('/cart')
        if path == '/cart/remove':
            cart.pop(data.get('sku', ''), None)
            return self.redirect('/cart')
        if path == '/cart/clear':
            cart.clear()
            return self.redirect('/cart')
        if path == '/checkout':
            if not cart or not data.get('name') or not data.get('email'):
                return self.redirect('/cart')
            payment = data.get('payment') if data.get('payment') in PAYMENTS else 'PayPal'
            order = add_order(data['name'].strip(), data['email'].strip(), payment, price_cart(list(cart.items())))
            cart.clear()
            return self.send(200, views.confirmation_page(order))
        return self.send(404, views.not_found())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port', type=int, default=8111)
    args = ap.parse_args()
    httpd = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print('Larder & Co dev server on http://127.0.0.1:%d/' % args.port, flush=True)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
'''

STYLE_CSS = """* { box-sizing: border-box; }
body { margin: 0; font: 15px/1.5 "DejaVu Sans", Arial, sans-serif; color: #2b2622; background: #fbf8f3; }
.wrap { max-width: 1040px; margin: 0 auto; padding: 0 20px; }
header { background: #3d5a40; color: #fff; }
header .wrap { display: flex; align-items: center; justify-content: space-between; height: 58px; }
.logo { color: #fff; font: bold 22px Georgia, serif; text-decoration: none; }
nav a { color: #e8efe5; margin-left: 22px; text-decoration: none; }
nav a.on { color: #fff; border-bottom: 2px solid #e2b04a; }
.badge { background: #e2b04a; color: #2b2622; border-radius: 9px; padding: 0 7px; font-size: 12px; }
h1 { font: bold 30px Georgia, serif; margin: 28px 0 8px; }
.lead { color: #6b625a; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin: 20px 0 40px; }
.card { background: #fff; border: 1px solid #e6dfd4; border-radius: 8px; padding: 16px; }
.card h3 { margin: 4px 0; font-size: 17px; } .card h3 a { color: inherit; text-decoration: none; }
.cat { text-transform: uppercase; font-size: 11px; letter-spacing: .08em; color: #8a7f73; }
.unit { color: #8a7f73; font-size: 13px; }
.price { margin: 8px 0; } .price.big { font-size: 22px; }
s { color: #9b9187; } .sale { color: #b5402f; }
.tag { background: #b5402f; color: #fff; font-size: 11px; border-radius: 4px; padding: 1px 5px; }
form.add input { width: 56px; padding: 4px; } button { background: #3d5a40; color: #fff; border: 0;
  border-radius: 5px; padding: 6px 12px; cursor: pointer; } button.link { background: none; color: #3d5a40; padding: 0; }
table { width: 100%; border-collapse: collapse; background: #fff; } th, td { padding: 9px 10px; border-bottom: 1px solid #eee5d8; text-align: left; }
th { font-size: 12px; text-transform: uppercase; color: #8a7f73; } .num { text-align: right; }
tfoot td { font-weight: bold; } tr.grand td { font-size: 18px; }
tr.cancelled td, tr.refunded td { color: #a39a90; text-decoration: line-through; }
.tabs a { margin-right: 14px; color: #3d5a40; } .tabs a.on { font-weight: bold; text-decoration: none; }
.actions { margin: 14px 0; } .muted { color: #8a7f73; }
.checkout label { display: block; margin: 8px 0; } .checkout input, .checkout select { margin-left: 8px; padding: 4px; }
footer { color: #a39a90; font-size: 12px; padding: 40px 20px; }
"""

PRICING_MD = """# Pricing rules

These are the rules the shop must follow. Product pages, the cart and the checkout must agree.

1. Prices are in EUR and include VAT. Internally all amounts are integer cents.
2. **Sale prices.** A product on sale has a percentage discount (`sale_pct` in `shop/catalog.py`). The sale unit
   price is the regular unit price minus the discount, rounded to the cent (halves round up). This is the price
   shown on the product page (`catalog.sale_price`).
3. **Line total** = sale unit price x quantity. The discount applies to *every* unit in the line.
4. **Subtotal** = sum of all line totals.
5. **Shipping** is a flat EUR 4.90, free when the subtotal (after sale discounts) is EUR 39.00 or more.
6. **Total** = subtotal + shipping.
"""

TEST_CART = """import unittest

from shop.cart import price_cart


class CartTest(unittest.TestCase):
    def test_regular_items(self):
        t = price_cart([('FLR-1K', 2), ('TEA-100', 1)])
        self.assertEqual(t.subtotal, 640 + 1150)
        self.assertEqual(t.shipping, 490)
        self.assertEqual(t.total, 640 + 1150 + 490)

    def test_single_sale_item(self):
        t = price_cart([('OIL-500', 1)])
        self.assertEqual(t.lines[0].unit_price, 840)
        self.assertEqual(t.lines[0].total, 840)

    def test_free_shipping_threshold(self):
        self.assertEqual(price_cart([('TEA-100', 3), ('FLR-1K', 2)]).shipping, 0)   # 34.50 + 6.40
        self.assertEqual(price_cart([('TEA-100', 3)]).shipping, 490)                 # 34.50

    def test_empty_cart(self):
        t = price_cart([])
        self.assertEqual((t.subtotal, t.shipping, t.total), (0, 0, 0))


if __name__ == '__main__':
    unittest.main()
"""

TEST_ORDERS = """import os
import tempfile
import unittest

from shop.cart import price_cart
from shop.orders import add_order, load_orders


class OrdersTest(unittest.TestCase):
    def test_add_order(self):
        path = os.path.join(tempfile.mkdtemp(), 'orders.json')
        with open(path, 'w') as f:
            f.write('[]')
        order = add_order('Test Person', 't@example.org', 'Card', price_cart([('FLR-1K', 1)]), path=path)
        self.assertEqual(order['id'], 1001)
        self.assertEqual(order['total'], 320 + 490)
        self.assertEqual(load_orders(path)[0]['customer'], 'Test Person')

    def test_seed_orders_are_valid(self):
        from shop.orders import SEED
        for o in load_orders(SEED):
            self.assertIn(o['status'], ('paid', 'cancelled', 'refunded'))
            self.assertRegex(o['created'], r'^2026-\\d\\d-\\d\\dT\\d\\d:\\d\\d$')


if __name__ == '__main__':
    unittest.main()
"""

README_1 = """# Larder & Co web shop

The online shop of Larder & Co Feinkost (Hamburg). Python 3 standard library only - no dependencies.

## Run it

    python3 -m shop.server --port 8111

then open http://127.0.0.1:8111/ . Pages: the shop (`/`), product pages (`/product/<sku>`), the cart and checkout
(`/cart`) and the orders admin page (`/orders?month=YYYY-MM`).

## Tests

    python3 -m unittest

## Layout

| path | what |
|---|---|
| `shop/catalog.py` | products, sale prices |
| `shop/cart.py` | cart pricing (see `docs/PRICING.md`) |
| `shop/orders.py` | order storage (`data/orders.json`, seeded from `data/orders.seed.json`) |
| `shop/views.py` | HTML pages |
| `shop/server.py` | HTTP routes |
"""

README_2 = README_1.replace("""## Run it

    python3 -m shop.server --port 8111

then open""", """## Run it

    ./dev.sh start        # also: stop, restart, status, log

or in the foreground `python3 -m shop.server --port 8111`, then open""").replace(
    "## Tests", "The dev server does not reload code: restart it (`./dev.sh restart`) after changing Python files.\n"
                "Carts are kept in memory, so a restart empties them.\n\n## Tests")

ISSUE_42 = """# Issue 42: cart total higher than the sale prices

Status: open
Reported: 2026-10-19 by Hanna (support)
Customer: Ingrid S. (did not place the order)

> Hello, I wanted to order a few things from your autumn sale, but the total in my cart is higher than what the
> product pages promise. I took a screenshot of my cart before giving up. Can you fix it? I would still like to
> order exactly these things.

Screenshot of her cart: `42-cart-screenshot.png` (this folder).

Hanna: I rebuilt her cart on the shop and got the same total. The prices on the product pages look right to me.
"""

GITIGNORE = "__pycache__/\n*.pyc\ndata/orders.json\ndata/orders.json.tmp\nlogs/\n.devserver.pid\n"


# ------------------------------------------------------------------ images
def cart_screenshot(path):
    lines, sub, ship, total = price_cart(CUSTOMER_CART, buggy=True)
    W, H = 1366, 860
    im = Image.new("RGB", (W, H), "#fbf8f3")
    d = ImageDraw.Draw(im)
    # browser chrome
    d.rectangle((0, 0, W, 78), fill="#dee1e6")
    d.rounded_rectangle((10, 6, 300, 38), 8, fill="#fbf8f3")
    d.text((26, 13), "Cart \u00b7 Larder & Co", fill="#333", font=font(15))
    d.rounded_rectangle((90, 44, W - 120, 72), 14, fill="#f1f3f4")
    d.text((110, 49), "larder-co.example/cart", fill="#444", font=font(15))
    # site header
    d.rectangle((0, 78, W, 136), fill="#3d5a40")
    d.text((163, 92), "Larder & Co", fill="white", font=font(24, serif=True, bold=True))
    x = 840
    for label in ("Shop", "Cart  10", "My account"):
        d.text((x, 99), label, fill="#e8efe5", font=font(16))
        x += 120
    d.text((163, 165), "Your cart", fill="#2b2622", font=font(32, serif=True, bold=True))
    x0, x1 = 163, 1203
    y = 230
    cols = [(x0 + 10, "PRODUCT"), (x0 + 560, "PRICE"), (x0 + 760, "QTY"), (x0 + 900, "TOTAL")]
    d.rectangle((x0, y - 12, x1, y + 470), fill="white")
    for cx, lab in cols:
        d.text((cx, y), lab, fill="#8a7f73", font=font(13))
    y += 36
    d.line((x0, y - 8, x1, y - 8), fill="#eee5d8", width=1)
    for sku, name, unit, price, pct, qty, tot in lines:
        d.text((x0 + 10, y + 6), name, fill="#2b2622", font=font(17))
        d.text((x0 + 14 + d.textlength(name, font=font(17)), y + 9), unit, fill="#8a7f73", font=font(13))
        if pct:
            old = euro(price)
            d.text((x0 + 530, y + 7), old, fill="#9b9187", font=font(16))
            w = d.textlength(old, font=font(16))
            d.line((x0 + 530, y + 17, x0 + 530 + w, y + 17), fill="#9b9187", width=1)
            d.text((x0 + 540 + w, y + 7), euro(sale_price(price, pct)), fill="#2b2622", font=font(16))
        else:
            d.text((x0 + 600, y + 7), euro(price), fill="#2b2622", font=font(16))
        d.text((x0 + 780, y + 7), str(qty), fill="#2b2622", font=font(16))
        t = euro(tot)
        d.text((x0 + 960 - d.textlength(t, font=font(16)), y + 7), t, fill="#2b2622", font=font(16))
        d.text((x0 + 975, y + 9), "remove", fill="#3d5a40", font=font(12))
        y += 50
        d.line((x0, y - 6, x1, y - 6), fill="#eee5d8", width=1)
    for label, val, size in (("Subtotal", euro(sub), 16), ("Shipping", "free" if not ship else euro(ship), 16),
                             ("Total", euro(total), 20)):
        d.text((x0 + 10, y + 8), label, fill="#2b2622", font=font(size, bold=True))
        d.text((x0 + 960 - d.textlength(val, font=font(size, bold=True)), y + 8), val, fill="#2b2622",
               font=font(size, bold=True))
        y += 46
    # the customer's red circle around the total
    d.ellipse((x0 + 860, y - 60, x0 + 990, y - 4), outline="#d0302b", width=4)
    d.text((163, y + 40), "Empty cart", fill="#3d5a40", font=font(15))
    d.text((163, y + 90), "Checkout", fill="#2b2622", font=font(24, serif=True, bold=True))
    im.save(path, optimize=True)


TEMPLATE_HEAD = ["Belegnr", "Belegdatum", "Kunde", "Menge", "Versand", "Brutto", "Zahlart"]


def template_png(path):
    W, H = 1500, 720
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 34), fill="#f0f0f0")
    d.text((12, 8), "Import-Vorlage Webshop.ods - LibreOffice Calc", fill="#222", font=font(15))
    d.rectangle((0, 34, W, 66), fill="#fafafa")
    d.text((12, 42), "A1", fill="#222", font=font(14))
    d.text((90, 42), "fx  Import-Vorlage Webshop -> Buchhaltung (Brandt & Partner Steuerberatung)", fill="#222",
           font=font(14))
    widths = [130, 150, 220, 90, 110, 120, 130]
    xs = [48]
    for w in widths:
        xs.append(xs[-1] + w)
    xs[-1] = max(xs[-1], 1060)
    top, rh = 70, 30
    d.rectangle((0, top, W, top + rh), fill="#e8e8e8")
    for i, x in enumerate(xs[:-1]):
        d.text((x + widths[i] // 2 - 5, top + 7), "ABCDEFG"[i], fill="#444", font=font(14))
    d.text((xs[-1] + 40, top + 7), "H", fill="#444", font=font(14))
    rows = [
        ["Import-Vorlage Webshop -> Buchhaltung (Brandt & Partner Steuerberatung)"],
        [],
        TEMPLATE_HEAD,
        ["LC-0998", "28.07.2026", "Max Mustermann", "3", "4,90", "27,40", "PayPal"],
        ["LC-0999", "30.07.2026", "Erika Musterfrau", "7", "0,00", "61,15", "Invoice"],
        [],
        ["Hinweise:"],
        ["- Trennzeichen Semikolon ( ; ), Zeichensatz UTF-8, erste Zeile = Spaltenköpfe genau wie oben"],
        ["- Beträge mit Dezimalkomma, ohne Währungszeichen und ohne Tausenderpunkt (z. B. 1234,50)"],
        ["- Belegdatum = Bestelldatum im Format TT.MM.JJJJ, Belegnr = LC- plus Bestellnummer"],
        ["- Menge = Summe der Stückzahlen aller Artikel der Bestellung"],
        ["- Versand und Brutto wie in der Bestellung gespeichert, Zahlart wie im Shop (PayPal / Card / Invoice)"],
        ["- Nur bezahlte Bestellungen - stornierte (cancelled) und erstattete (refunded) NICHT exportieren"],
        ["- Eine Datei pro Kalendermonat, sortiert nach Datum (älteste zuerst)"],
    ]
    for r, cells in enumerate(rows):
        y = top + rh * (r + 1)
        d.rectangle((0, y, 46, y + rh), fill="#e8e8e8")
        d.text((14, y + 7), str(r + 1), fill="#444", font=font(13))
        for x in xs:
            d.line((x, y, x, y + rh), fill="#d4d4d4")
        d.line((0, y + rh, W, y + rh), fill="#d4d4d4")
        if r == 2:
            d.rectangle((xs[0] + 1, y + 1, xs[7] - 1, y + rh - 1), fill="#dde8f5")
        for c, txt in enumerate(cells):
            bold = r in (0, 2, 6)
            f = font(15, bold=bold)
            if c in (3, 4, 5) and r in (3, 4):
                d.text((xs[c + 1] - 8 - d.textlength(txt, font=f), y + 6), txt, fill="#111", font=f)
            else:
                d.text((xs[c] + 6, y + 6), txt, fill="#111", font=f)
    d.rectangle((0, H - 30, W, H), fill="#f0f0f0")
    d.text((12, H - 24), "Tabelle1", fill="#222", font=font(14))
    im.save(path, optimize=True)


# ------------------------------------------------------------------ seed orders
def seed_orders():
    r = random.Random(4211)
    names = ["Anna Weber", "Jonas Petersen", "Lena M\u00fcller", "Ole Hansen", "Sophie Becker", "Malte Schr\u00f6der",
             "Clara Jensen", "Finn Lorenz", "Ida Brandt", "Paul Neumann", "Greta Wolff", "Henrik Lund",
             "Mia Krause", "Theo Albers", "Emma Vogel", "Lukas Frey"]
    orders = []
    day = dt.datetime(2026, 8, 1, 9, 0)
    oid = 1001
    while True:
        day += dt.timedelta(hours=r.randint(30, 70), minutes=r.randint(0, 59))
        if day > dt.datetime(2026, 10, 21, 18, 0):
            break
        if not 8 <= day.hour <= 21:
            day = day.replace(hour=r.randint(8, 21))
        items = []
        for p in r.sample(PRODUCTS, r.randint(1, 4)):
            sale = p[4] if day >= dt.datetime(2026, 9, 14) else 0
            items.append({"sku": p[0], "qty": r.choice([1, 1, 1, 2, 2, 3, 4, 6]), "unit": sale_price(p[3], sale)})
        sub = sum(i["unit"] * i["qty"] for i in items)
        ship = 0 if sub >= FREE_FROM else SHIPPING
        name = r.choice(names)
        status = r.choices(["paid", "cancelled", "refunded"], [17, 2, 1])[0]
        orders.append({"id": oid, "created": day.strftime("%Y-%m-%dT%H:%M"), "customer": name,
                       "email": name.lower().replace(" ", ".").replace("\u00fc", "ue").replace("\u00f6", "oe") + "@example.org",
                       "items": items, "shipping": ship, "total": sub + ship,
                       "payment": r.choice(["PayPal", "PayPal", "Card", "Invoice"]), "status": status})
        oid += 1
    # make sure October has every kind of row the template talks about
    octo = [o for o in orders if o["created"].startswith("2026-10")]
    octo[2]["status"], octo[5]["status"] = "cancelled", "refunded"
    return orders


def money(c):
    return f"{c // 100},{c % 100:02d}"


def export_rows(orders, month):
    rows = []
    for o in sorted(orders, key=lambda o: (o["created"], o["id"])):
        if o["status"] != "paid" or o["created"][:7] != month:
            continue
        y, m, d = o["created"][:10].split("-")
        rows.append([f"LC-{o['id']}", f"{d}.{m}.{y}", o["customer"], str(sum(i["qty"] for i in o["items"])),
                     money(o["shipping"]), money(o["total"]), o["payment"]])
    return rows


def build(out):
    os.makedirs(out, exist_ok=True)
    tmp_png = os.path.join(out, "_cart.png")
    tmp_tpl = os.path.join(out, "_tpl.png")
    cart_screenshot(tmp_png)
    template_png(tmp_tpl)
    orders = seed_orders()
    base_files = {
        ".gitignore": GITIGNORE, "README.md": README_1, "shop/__init__.py": "", "shop/catalog.py": catalog_py(False),
        "shop/cart.py": CART_PY, "shop/orders.py": ORDERS_PY, "shop/views.py": VIEWS_PY, "shop/server.py": SERVER_PY,
        "shop/static/style.css": STYLE_CSS, "tests/__init__.py": "", "tests/test_cart.py": TEST_CART,
        "tests/test_orders.py": TEST_ORDERS,
        "data/orders.seed.json": json.dumps([o for o in orders if o["created"] < "2026-08-02"], indent=1, ensure_ascii=False),
    }
    history = [
        ("2026-08-02T11:20:00", MARA, base_files, "Initial shop: catalogue, cart, checkout and orders admin"),
        ("2026-09-14T16:05:00", TOBIAS, {"shop/catalog.py": catalog_py(True)}, "Autumn sale: per-product sale prices"),
        ("2026-10-02T09:40:00", MARA, {"docs/PRICING.md": PRICING_MD}, "Document the pricing rules"),
        ("2026-10-08T18:12:00", MARA, {"dev.sh": dev_sh("shop.server", PORT, "Larder & Co shop"), "README.md": README_2},
         "Add dev.sh to manage the local dev server"),
        ("2026-10-19T14:30:00", HANNA, {"issues/ISSUE-42.md": ISSUE_42,
                                        "issues/42-cart-screenshot.png": open(tmp_png, "rb").read()},
         "Add issue 42 from support"),
        ("2026-10-21T19:02:00", MARA, {"data/orders.seed.json": json.dumps(orders, indent=1, ensure_ascii=False),
                                       "docs/requests/bookkeeping-import-template.png": open(tmp_tpl, "rb").read()},
         "Refresh seed orders; add the bookkeeper's import template"),
    ]
    info = make_repo(os.path.join(out, "larder-shop.tar.gz"), "larder-shop", history, MARA)
    os.remove(tmp_png)
    os.remove(tmp_tpl)
    scenarios = [CUSTOMER_CART, [("CAP-90", 5), ("HON-250", 2)], [("PAP-75", 3)], [("VIN-250", 2), ("TEA-100", 1)],
                 [("OIL-500", 5)], [("COF-250", 3), ("CHO-100", 2)], []]
    exp_s = []
    for sc in scenarios:
        _, sub, ship, tot = price_cart(sc)
        exp_s.append({"items": sc, "subtotal": sub, "shipping": ship, "total": tot})
    json.dump({"base": info["base"], "port": PORT, "customer_cart": CUSTOMER_CART,
               "customer_total": price_cart(CUSTOMER_CART)[3], "customer_buggy_total": price_cart(CUSTOMER_CART, True)[3],
               "scenarios": exp_s, "template_head": TEMPLATE_HEAD,
               "export_months": {m: export_rows(orders, m) for m in ("2026-08", "2026-09", "2026-10")}},
              open(os.path.join(out, "expected.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/d1_build")
