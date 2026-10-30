from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.solar_cover.core.lux import LuxFilter
from custom_components.solar_cover.core.motion import MoveStatus, plan_move

T0 = datetime(2026, 10, 30, 18, 0, tzinfo=UTC)
DELAY = timedelta(minutes=3)


def run(filter_: LuxFilter, minute: float, lux: float | None) -> bool:
    return filter_.update(T0 + timedelta(minutes=minute), lux, 1000, 400, DELAY)


def test_liga_so_depois_do_atraso() -> None:
    f = LuxFilter()
    assert run(f, 0, 1200) is False
    assert run(f, 2.9, 1200) is False
    assert run(f, 3, 1200) is True


def test_oscilacao_curta_zera_a_contagem() -> None:
    f = LuxFilter()
    run(f, 0, 1200)
    run(f, 2, 900)  # caiu abaixo do limiar de ligar: cancela
    assert run(f, 3.5, 1200) is False  # recomeçou a contar em 3,5
    assert run(f, 6.5, 1200) is True


def test_histerese_mantem_ligado_entre_os_limiares() -> None:
    f = LuxFilter(state=True)
    for minute in range(0, 20):
        assert run(f, minute, 600) is True  # entre 400 e 1000: nada muda


def test_desliga_abaixo_do_limiar_inferior_com_atraso() -> None:
    f = LuxFilter(state=True)
    assert run(f, 0, 300) is True
    assert run(f, 3, 300) is False


def test_sensor_indisponivel_mantem_estado() -> None:
    f = LuxFilter(state=True)
    assert run(f, 0, None) is True
    assert run(f, 100, None) is True


def test_limiar_inferior_maior_que_o_superior_e_corrigido() -> None:
    f = LuxFilter()
    assert f.update(T0, 1200, 1000, 5000, timedelta(0)) is True
    # off (5000) > on (1000) é corrigido para off = on = 1000, então 999 já desliga
    assert f.update(T0, 999, 1000, 5000, timedelta(0)) is False


def plan(**overrides):
    base = {
        "current": 50.0,
        "desired": 50,
        "now": T0,
        "last_move": None,
        "tolerance": 5.0,
        "min_interval": timedelta(minutes=3),
        "moving": False,
    }
    base.update(overrides)
    return plan_move(**base)


def test_sem_posicao_ou_em_movimento_nao_age() -> None:
    assert plan(current=None).status is MoveStatus.UNAVAILABLE
    assert plan(moving=True, desired=0).status is MoveStatus.MOVING


def test_dentro_da_tolerancia_nao_move() -> None:
    assert plan(desired=50).status is MoveStatus.IDLE
    assert plan(desired=54).status is MoveStatus.IDLE


def test_aberta_demais_fecha_com_folga_e_sem_esperar() -> None:
    result = plan(desired=40, last_move=T0 - timedelta(seconds=5))
    assert result.status is MoveStatus.MOVE
    assert result.target == 37  # desired - (tolerância - 2), para o próximo ajuste demorar


def test_abre_apenas_com_diferenca_e_intervalo_minimo() -> None:
    assert plan(desired=55).status is MoveStatus.MOVE
    assert plan(desired=55).target == 55
    waiting = plan(desired=60, last_move=T0 - timedelta(minutes=1))
    assert waiting.status is MoveStatus.WAITING
    assert plan(desired=60, last_move=T0 - timedelta(minutes=4)).status is MoveStatus.MOVE


def test_fechar_passando_do_ponto_nunca_causa_reabertura() -> None:
    """Sol em queda, com o ruído de arredondamento do desejado: só fecha, nunca reabre."""
    for tolerance in (0.0, 2.0, 3.0, 5.0, 8.0, 15.0):
        current = 100.0
        for step in range(400):
            desired = max(0, 100 - step * 0.37)
            for noise in (-0.4, 0.0, 0.4):  # round() oscila no máximo 1 ponto
                result = plan(
                    current=current,
                    desired=round(min(100, max(0, desired + noise))),
                    tolerance=tolerance,
                    last_move=None,
                )
                if result.status is MoveStatus.MOVE:
                    assert result.target <= round(current), (tolerance, step, noise)
                    current = float(result.target)


def test_fechar_sempre_deixa_a_cortina_abaixo_do_desejado() -> None:
    for tolerance in (1.0, 5.0, 12.0):
        for desired in range(0, 101, 7):
            result = plan(current=100.0, desired=desired, tolerance=tolerance)
            if result.status is MoveStatus.MOVE:
                assert 0 <= result.target <= desired


def test_extremos() -> None:
    assert plan(current=3, desired=0).target == 0
    assert plan(current=3, desired=2).target == 0  # nunca abaixo de 0
    assert plan(current=98, desired=100).status is MoveStatus.IDLE
    assert plan(current=90, desired=100).target == 100


def test_tolerancia_minima_e_dois_pontos() -> None:
    assert plan(tolerance=0, desired=52).status is MoveStatus.MOVE
    assert plan(tolerance=0, desired=51).status is MoveStatus.IDLE
