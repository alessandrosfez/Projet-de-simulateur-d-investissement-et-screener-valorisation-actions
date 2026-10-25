"""
Tests des graphiques (charts.py) : structure des figures, pas leur rendu. On vérifie ce qui
changerait la lecture : une donnée manquante qui ne devient jamais 0, un score indicatif
distingué d'un score officiel, des zones posées aux seuils demandés.
Usage : pip install -r requirements-dev.txt && pytest -v
"""
import layout
from charts import make_income_vs_cfo_chart, make_score_zone_chart


def _zones():
    return [
        {"start": None, "end": 1.81, "status": "critical", "label": "détresse"},
        {"start": 1.81, "end": 2.99, "status": "warning", "label": "grise"},
        {"start": 2.99, "end": None, "status": "good", "label": "sûre"},
    ]


def test_score_zone_chart_one_point_per_year_and_bands_at_thresholds():
    points = [{"label": "2024", "value": 3.4, "hollow": False, "hover": "a"},
              {"label": "2023", "value": 1.2, "hollow": True, "hover": "b"}]
    fig = make_score_zone_chart(points, _zones(), "Z", lambda v: f"{v:.2f}")
    markers = fig.data[-1]
    assert list(markers.x) == [3.4, 1.2]
    assert list(markers.marker.symbol) == ["circle", "circle-open"]
    bands = [s for s in fig.layout.shapes if s.type == "rect"]
    assert len(bands) == 3
    assert (bands[1].x0, bands[1].x1) == (1.81, 2.99)
    # Les zones ouvertes vont jusqu'au bord de l'axe, qui encadre points et seuils.
    low, high = fig.layout.xaxis.range
    assert bands[0].x0 == low < 1.2 and bands[2].x1 == high > 3.4


def test_income_vs_cfo_chart_keeps_missing_values_missing_and_scales_axis():
    fig = make_income_vs_cfo_chart(["2023", "2024"], [2.0e9, None], [2.5e9, 1.0e9], ("RN", "CFO"), "t",
                                   lambda v: "n.d." if v is None else f"{v:.0f}", ("Md", "M"))
    net_income, cfo = fig.data
    assert list(net_income.y) == [2.0, None]
    assert list(cfo.y) == [2.5, 1.0]
    assert fig.layout.yaxis.ticksuffix == " Md"
    assert list(net_income.customdata) == ["2000000000", "n.d."]


def test_spark_text_follows_the_values_and_marks_missing_years():
    assert layout.spark_text([1.0, 2.0, 3.0]) == "▁▅█"
    assert layout.spark_text([1.2, None, 1.5]) == "▁·█"
    assert layout.spark_text([5.0]) == ""


def test_trend_state_uses_the_favourable_direction_of_each_ratio():
    assert layout.trend_state("dso", -5.0) == "good"          # clients payés plus vite
    assert layout.trend_state("cfo_to_net_income", -0.2) == "bad"
    assert layout.trend_state("dpo", 4.0) == "neutral"        # lecture non univoque
    assert layout.trend_state("ccc", None) == "neutral"
