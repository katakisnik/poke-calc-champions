import pytest

from poke_calc.data.loader import load_dex
from poke_calc.data.regulations import _BANNED_IN_REG_M_A, is_item_legal, legal_items


class TestRegulationCounts:
    def test_exactly_31_items_banned_in_reg_m_a(self):
        # Matches championsregma/items.ts's 31 entries exactly (verified
        # against the live source this session - see module docstring).
        assert len(_BANNED_IN_REG_M_A) == 31

    def test_reg_m_b_is_the_full_dex(self):
        dex = load_dex()
        assert len(legal_items(dex, "M-B")) == len(dex.items)

    def test_reg_m_a_excludes_exactly_the_banned_set(self):
        dex = load_dex()
        m_a = legal_items(dex, "M-A")
        assert len(dex.items) - len(m_a) == 31


class TestKnownItems:
    @pytest.mark.parametrize("item_id", ["lifeorb", "ironball", "muscleband", "expertbelt", "mawilite"])
    def test_banned_in_m_a_legal_in_m_b(self, item_id):
        assert is_item_legal(item_id, "M-A") is False
        assert is_item_legal(item_id, "M-B") is True

    @pytest.mark.parametrize("item_id", ["choicescarf", "leftovers", "focussash", "meganiumite"])
    def test_legal_in_both(self, item_id):
        assert is_item_legal(item_id, "M-A") is True
        assert is_item_legal(item_id, "M-B") is True


class TestInputValidation:
    def test_unknown_regulation_rejected(self):
        with pytest.raises(ValueError, match="unknown regulation"):
            is_item_legal("lifeorb", "M-C")
