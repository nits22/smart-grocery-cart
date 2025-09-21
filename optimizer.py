# optimizer.py
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpBinary

def greedy_optimize(price_table, delivery_fees=None, max_stores=None):
    """
    price_table: dict item -> {store: {'price': float, 'available': bool}}
    delivery_fees: dict store -> fee (or 0)
    returns dict {item: (store, price)}
    """
    result = {}
    for item, stores in price_table.items():
        best = None
        for s, info in stores.items():
            if not info['available']:
                continue
            if best is None or info['price'] < best[1]:
                best = (s, info['price'])
        result[item] = best  # could be None if unavailable
    return result

def ilp_optimize(price_table, delivery_fees=None):
    # Flatten
    items = list(price_table.keys())
    stores = set()
    for it in items:
        stores.update(price_table[it].keys())
    stores = list(stores)
    if delivery_fees is None:
        delivery_fees = {s:0 for s in stores}

    # create variables
    prob = LpProblem("grocery_cart", LpMinimize)
    x = {}  # x[(i,s)] = 1 if item i bought from s
    y = {}  # y[s] = 1 if store s used
    for i in items:
        for s in stores:
            x[(i,s)] = LpVariable(f"x_{i}_{s}", cat=LpBinary)
    for s in stores:
        y[s] = LpVariable(f"y_{s}", cat=LpBinary)

    # objective: sum prices*x + sum delivery*y
    prob += lpSum([
        (price_table[i][s]['price'] if price_table[i][s]['available'] else 1e6) * x[(i,s)]
        for i in items for s in stores
    ]) + lpSum([delivery_fees.get(s,0)*y[s] for s in stores])

    # constraints: each item must be bought exactly once (or allow skipping unavailable)
    for i in items:
        prob += lpSum([ x[(i,s)] for s in stores ]) == 1

    # link x and y: x_{i,s} <= y_s
    for i in items:
        for s in stores:
            prob += x[(i,s)] <= y[s]

    prob.solve()
    result = {}
    for i in items:
        for s in stores:
            if x[(i,s)].value() == 1.0:
                result[i] = (s, price_table[i][s]['price'])
    return result
