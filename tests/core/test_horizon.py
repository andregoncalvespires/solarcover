from __future__ import annotations

import pytest

from custom_components.solar_cover.core.horizon import HorizonProfile


def test_vazio_nao_obstrui() -> None:
    assert HorizonProfile.parse("").elevation_at(270) == 0
    assert HorizonProfile.parse(None).elevation_at(270) == 0
    assert HorizonProfile().elevation_at(270) == 0


def test_interpolacao_linear_e_fora_do_intervalo() -> None:
    profile = HorizonProfile.parse("250:10; 270:20; 290:20; 300:0")
    assert profile.elevation_at(250) == 10
    assert profile.elevation_at(260) == pytest.approx(15)
    assert profile.elevation_at(280) == 20
    assert profile.elevation_at(295) == pytest.approx(10)
    assert profile.elevation_at(300) == 0
    assert profile.elevation_at(249.9) == 0
    assert profile.elevation_at(300.1) == 0
    assert profile.elevation_at(-90) == 20  # -90° normaliza para 270°, dentro do perfil


def test_degrau_de_quina_vertical() -> None:
    profile = HorizonProfile.parse("250:0; 250:18; 280:18; 280:0")
    assert profile.elevation_at(249.9) == 0
    assert profile.elevation_at(250) == 18
    assert profile.elevation_at(279.9) == 18
    assert profile.elevation_at(280) == 0


def test_regra_antiga_vira_perfil_plano() -> None:
    # faixa de azimute do prédio com topo a 15°, como na regra empírica anterior
    profile = HorizonProfile.parse("262:15; 291:15")
    assert profile.elevation_at(270) == 15
    assert profile.elevation_at(291) == 15
    assert profile.elevation_at(292) == 0


def test_aceita_virgula_decimal_e_quebra_de_linha_e_ordena() -> None:
    profile = HorizonProfile.parse("290:12,5\n250: 10")
    assert profile.points == ((250.0, 10.0), (290.0, 12.5))


def test_texto_ida_e_volta() -> None:
    profile = HorizonProfile.parse("250:10; 270:20.5")
    assert HorizonProfile.parse(profile.to_text()) == profile


@pytest.mark.parametrize(
    "text",
    ["250", "250:10", "a:b; 1:2", "400:10; 410:10", "250:95; 260:10", "1:2:3; 4:5"],
)
def test_formato_invalido(text: str) -> None:
    with pytest.raises(ValueError):
        HorizonProfile.parse(text)
