from src.ps_dtw import ps_dtw_similarity

def test_ps_dtw_identical():
    seq = [60, 80, -1500, -300, 90]
    assert ps_dtw_similarity(seq, seq) > 0.99
