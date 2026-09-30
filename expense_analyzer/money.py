from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
CUATRO_DECIMALES = Decimal("0.0001")


def _normalizar_numero_texto(valor: str) -> str:
    texto = valor.strip().replace("$", "").replace(" ", "").replace("USD", "")
    if not texto:
        return ""
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            return texto.replace(".", "").replace(",", ".")
        return texto.replace(",", "")
    if "," in texto:
        partes = texto.split(",")
        if len(partes) == 2 and len(partes[1]) != 3:
            return texto.replace(",", ".")
        return texto.replace(",", "")
    return texto


def to_decimal(valor) -> Decimal:
    if isinstance(valor, Decimal):
        return valor
    if valor is None or valor == "":
        return Decimal("0")
    if isinstance(valor, bool):
        return Decimal("1") if valor else Decimal("0")
    if isinstance(valor, float):
        try:
            return Decimal(repr(float(valor)))
        except (InvalidOperation, ValueError, ArithmeticError):
            return Decimal("0")
    if isinstance(valor, int):
        return Decimal(valor)
    try:
        return Decimal(_normalizar_numero_texto(str(valor)) or "0")
    except (InvalidOperation, ValueError, ArithmeticError):
        return Decimal("0")


def to_money(valor) -> Decimal:
    return to_decimal(valor).quantize(CENT, rounding=ROUND_HALF_UP)


def to_cantidad(valor) -> Decimal:
    return to_decimal(valor).quantize(CUATRO_DECIMALES, rounding=ROUND_HALF_UP)


def line_total(cantidad, precio_unitario) -> Decimal:
    return to_money(to_decimal(cantidad) * to_decimal(precio_unitario))


def invoice_total(items) -> Decimal:
    total = Decimal("0")
    for item in items:
        total += line_total(item.get("cantidad"), item.get("precio_unitario"))
    return to_money(total)
