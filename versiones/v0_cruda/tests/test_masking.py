"""RF-16 … RF-18."""
import pytest

from app.masking import enmascarar, luhn_valido, rut_valido


def test_digito_verificador():
    assert rut_valido("12.345.678", "5")
    assert rut_valido("9876545", "k")
    assert not rut_valido("12.345.678", "9")


def test_luhn():
    assert luhn_valido("4111 1111 1111 1111")
    assert not luhn_valido("4111 1111 1111 1112")


@pytest.mark.parametrize("texto,valor,tipo", [
    ("mi rut es 12.345.678-5", "12.345.678-5", "rut"),
    ("RUT 9.876.545-K por favor", "9.876.545-K", "rut"),
    ("mi run es 123456785", "123456785", "rut"),
    ("pagué con la tarjeta 4111 1111 1111 1111", "4111 1111 1111 1111", "tarjeta"),
    ("tarjeta 5500-0000-0000-0004", "5500-0000-0000-0004", "tarjeta"),
    ("transfiere a la cuenta corriente 00123456789", "00123456789", "cuenta"),
    ("cuenta n° 987654321", "987654321", "cuenta"),
    ("escríbeme a jperez@gmail.com", "jperez@gmail.com", "correo"),
    ("mi celular es +56 9 8765 4321", "8765 4321", "telefono"),
    ("mi clave del banco es Perro1234", "Perro1234", "clave"),
    ("el cvv: 123", "cvv: 123", "clave"),
])
def test_enmascara(texto, valor, tipo):
    r = enmascarar(texto)
    assert valor not in r.texto
    assert tipo in r.tipos


@pytest.mark.parametrize("texto", [
    "gasté $1.200.000 en el arriendo",
    "gasté 25 lucas en el súper",
    "compré 10 acciones a 41.000",
    "mi sueldo es 1.850.000",
    "pagué la cuenta de la luz",
    "la cuenta del restaurante fue 125000",
])
def test_no_enmascara_montos(texto):
    r = enmascarar(texto)
    assert r.texto == texto
    assert r.tipos == []


def test_rut_invalido_sin_contexto_no_se_toca():
    assert enmascarar("código 12.345.678-9").tipos == []
