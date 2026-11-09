# Merchant stock survives a screen change

Status: **implemented.** Issue #24. Leaving a merchant and walking back
does not refill what was bought.

## Rule

The four dungeon shelves and the four village-market shelves record a sale
in `run_state.shop_bought`. The arrival chart and the smith's quarter
(forge, vamp, rune) record theirs in `run_state.shop_civic`. Both bytes
clear when the next dungeon begins. The market nibble and the civic byte
also clear when a new Rift Wild region begins. A rebuilt room skips a bought
shelf and its floor price. Unique wares bought earlier are still skipped by
the featured-ware walk, and a sold unique does not get replaced by the next
unowned relic on the same visit.

Older suspends omit the bytes and load as nothing bought. The save grows by
two appended bytes.

## Evidence

`scripts/test_merchant_stock.py` buys two dungeon shelves, leaves, returns,
and checks those shelves stay empty while the other two keep their ware and
price.
