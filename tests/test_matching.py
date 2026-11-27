from app.matching import Canonical, match_title, parse_title, precio_por_ml

ACQUA = Canonical("Giorgio Armani", "Acqua di Gio", "edt")
SAUVAGE = Canonical("Dior", "Sauvage", "edp")
CATALOG = [ACQUA, SAUVAGE]


def test_parse_strips_concentration_and_size():
    parsed = parse_title("Giorgio Armani Acqua di Gio Eau de Toilette 100 ml")
    assert parsed.concentracion == "edt"
    assert parsed.ml == 100
    assert parsed.nombre_normalizado == "giorgio armani acqua di gio"


def test_retailer_title_matches_canonical():
    result = match_title(
        "ARMANI ACQUA DI GIO EDT 100ML HOMBRE",
        CATALOG,
    )
    assert result.status == "matched"
    assert result.canonical == ACQUA
    assert result.parsed.ml == 100
    assert result.score >= 92


def test_clean_title_matches():
    result = match_title("Acqua di Gio Eau de Toilette 50 ml", CATALOG)
    assert result.status == "matched"
    assert result.canonical == ACQUA
    assert result.parsed.ml == 50


def test_sizes_share_canonical_but_stay_on_the_offer():
    small = match_title("Acqua di Gio EDT 50 ml", CATALOG)
    big = match_title("Acqua di Gio EDT 100 ml", CATALOG)
    assert small.canonical == big.canonical == ACQUA
    assert small.parsed.ml == 50
    assert big.parsed.ml == 100
    assert precio_por_ml(39990, 50) == 800
    assert precio_por_ml(59990, 100) == 600


def test_flanker_does_not_auto_match():
    result = match_title("Acqua di Gio Profondo EDT 100 ml", CATALOG)
    assert result.status != "matched"
    assert result.score < 92


def test_other_perfume_stays_below_auto_match():
    result = match_title("Dior Sauvage Eau de Parfum 100 ml", CATALOG)
    assert result.status == "matched"
    assert result.canonical == SAUVAGE

    other = match_title("Bleu de Chanel EDP 100 ml", CATALOG)
    assert other.status != "matched"
    assert other.score < 92


def test_near_name_goes_to_review_not_auto():
    result = match_title("Acqua di Gioia EDT 100 ml", CATALOG)
    assert result.status != "matched"


def test_missing_size_does_not_invent_price_per_ml():
    assert precio_por_ml(59990, None) is None
    parsed = parse_title("Acqua di Gio EDT")
    assert parsed.ml is None
