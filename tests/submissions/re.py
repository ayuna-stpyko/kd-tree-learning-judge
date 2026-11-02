# 期待: RE (RecursionError)
def f(n):
    return f(n + 1)
f(0)
