from gmst.segment.turns import TurnTracker


def test_no_bump_within_gap():
    t = TurnTracker(gap_seconds=1.5)
    assert t.update(0.0, 2.0) == 1
    assert t.update(2.5, 4.0) == 1      # 0.5 s gap
    assert t.turn == 1


def test_bump_on_long_pause():
    t = TurnTracker(gap_seconds=1.5)
    t.update(0.0, 2.0)
    assert t.update(4.0, 5.0) == 2      # 2.0 s gap
    assert t.update(5.2, 6.0) == 2
    assert t.update(10.0, 11.0) == 3


def test_zero_gap_disables_bumping():
    t = TurnTracker(gap_seconds=0.0)
    t.update(0.0, 1.0)
    assert t.update(100.0, 101.0) == 1


def test_out_of_order_end_does_not_rewind_last_end():
    t = TurnTracker(gap_seconds=1.0)
    t.update(0.0, 5.0)
    t.update(1.0, 2.0)                  # overlapping/late span
    assert t.update(5.5, 6.0) == 1      # measured from 5.0, not 2.0
