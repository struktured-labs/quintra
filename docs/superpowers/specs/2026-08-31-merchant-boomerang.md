# Merchant Boomerang

## Player contract

- Dungeon merchants can stock a run-long **Boomerang** relic for 30 coins.
- A ready, valid champion signature remains the first result of a B press.
- If B is cooling down, muted, or a targeted signature has no target, B throws
  the Boomerang instead.
- Only one Boomerang can exist at once. It travels about seven tiles, turns at
  that limit or on solid terrain, then homes to the moving champion and can be
  thrown again after it is caught.

## Interactions

- Contact briefly Stops an ordinary enemy without dealing damage.
- Elite, alpha, miniboss, and Colossus bodies are immune.
- The Boomerang cuts hostile projectiles without being consumed.
- It carries ordinary loose hearts, coins, MP, items, and Surge pickups to the
  champion. Shops, choices, progression objects, Wildcards, and residents are
  never moved.
- It cannot open secrets, break pots or crystals, press switches, or damage a
  boss. The mechanic is utility and crowd control, not another damage stack.

## Cartridge constraints

- The projectile uses one entity slot, one dedicated 8x8 OBJ tile, and existing
  projectile/status collision systems.
- Ownership is checked from the 16-slot run inventory only on a B edge; no
  per-frame inventory scan is added.
- Merchant selection remains seed-pure and advances past an already owned copy.

## Verification

- Content validation includes the new stable item ID.
- The live-ROM merchant test covers the complete featured-stock catalog, price,
  art, atomic purchase, one-projectile limit, outbound/return travel, ordinary
  enemy Stop, elite immunity, hostile-shot cutting, and loose-loot retrieval.
