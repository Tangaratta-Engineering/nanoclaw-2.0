<!-- Source: George's compiled guide from the official Hooded Horse wiki, read 15 Nov 2026. Newer than hints-and-missions.md: when numbers differ, trust this file. -->

# Empires of the Undergrowth: Mechanics & Strategy Guide


## Overview and game modes

Empires of the Undergrowth is a real-time-strategy colony builder: ants dig and build chambers underground, store food and raise brood, then claim surface territory and fight enemies and rival colonies. The community wiki says nest design, colony size, army composition and attack timing are the keys to victory. This guide is compiled from the [official community wiki](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Main_Page); where a tip is my own inference from those mechanics rather than stated on the wiki, it is marked as such.

### Game modes

| Mode | What it is | Notes |
| --- | --- | --- |
| [Story mode](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Story_Mode) | Main campaign: a hub formicarium plus documentary missions and formicarium challenges | Spend Royal Jelly on adaptations; New Game Plus unlocks after the final trial |
| [Arcade mode](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Arcade_Mode) | Demo missions, extra missions, Battle Arena and Remix missions | Remix does not touch story saves and gives no achievements |
| [Custom game](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Custom_Game_Mode) | Sandbox skirmish with your own settings | Uses custom-game-mode stats |
| DLC | Two extra colonies beyond the nine in the base game | See the wiki's Paid Extra Content page |

### Objectives

You must finish every compulsory objective, and you lose instantly if the queen dies. Objective types are: eliminate certain enemies, survive for a set time, survive attack waves, gather resources, clear all resources in an area, and keep certain conditions until the end (failing the last loses the mission even if the queen lives). Gathered resources only count once stored, and refunds do not count ([Mission Difficulty Setting](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Mission_Difficulty_Setting)).

### Difficulty

- Most missions offer easy, medium, hard, extreme and impossible. The wiki recommends medium for a first playthrough.
- Higher difficulty means scarcer resources, harder objectives, more and larger swarm enemies arriving sooner, shorter preparation periods between waves, bigger and tougher titans, and AI colonies that are more aggressive, get a bigger head start and cheat more often.
- Easy halves enemy health and doubles the food they drop.
- You cannot save mid-mission. In most missions edible corpses do not decay, while plants and lignocellulose do not regrow, so resources are finite.
- Each New Game Plus powerscales swarm enemies by +1 star level, bosses such as titans by +2, and gives AI colonies a bigger head start.
- Achievements come from extra objectives on a designated difficulty or higher. They do not affect rewards or story progression, and you can earn them in New Game Plus. Turn on achievement tracking to see whether you are meeting or failing each one mid-mission.

### Story mode structure

- **Hub formicarium:** your gene-thief ant colony lives here. Beating missions earns resources usable only here: Royal Jelly (customisation), territory points (one per tile you can dig) and food drops (seeds, woodworms, woodlice). After finishing a chapter a spawning menu lets you release past enemies to test your colony; they are not edible.
- **Population cap:** the number of brood tiles you may build is capped at 100, 125, 150, 175 and 300 by chapter.
- **Chapter transitions:** entering chapters 3, 4 and 5 moves your queen to a new formicarium with almost no resources. You are paid Royal Jelly equal to unused territory points, excavated tiles, 1.25% of total construction cost and 1.25% of food in the previous formicarium.
- **Documentary missions** (your adaptations are not applied): black ants in an English woodland, wood ants on a French beach, leafcutter ants in an Ecuadorian rainforest, fire ants in Green Swamp Preserve, Matabele ants and then termites on an Ivorian savannah. Beating one for the first time, with and without Challenge mode, earns extra resources.
- **Formicarium challenges** (your adaptations are applied): The First, Second, Final and REAL Final Experiments, plus Possibly the Final Experiment. You only earn resources on the first win, and edible enemies become inedible on replays. Failing returns you to just before the attempt, and quitting midway forfeits resources you spent.
- **New Game Plus** unlocks after The REAL Final Experiment and cannot be undone. You replay the story keeping all units, adaptations, minor improvements and Royal Jelly.

### Arcade mode details

- **Demo missions:** Tutorial, Critters and The Nest, Hold Out and Surrounded, The Crucible, The Promised Land. Good for learning controls.
- **Extra missions:** traditional ones (Aggrandise, Babysitting, Extremis, The Other Foot, Excavators, Occupation 1 and 2, Cramped, The Culling 1 and 2, Hibernation, Adventure, Firebreak, No Ant's Land, Chowder) and unusual ones (Tug of War 1 to 3, Enemy of My Enemy 1 and 2, Beetles Rise Up!). They contain late-story spoilers and often fix your unit choices.
- **Battle Arena:** pit creatures against each other. Up to 50 per click, level up to 3, star level up to 14; hold an icon 5 seconds for uber creatures. It uses story-mode stats.
- **Remix missions:** replay story, extra and demo missions with New Game Plus up to level 10, choice of story or custom stats, and your own custom colony. Custom leafcutters need harvestable plants, custom termites need lignocellulose, and custom fire ants need floating bridges to be required.

## Core mechanics

You win by keeping the queen alive and out-growing or out-fighting the objective; you lose the moment she dies. Everything below is taken from the [Basic Mechanics](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Basic_Mechanics) page unless noted, and individual missions may bend these rules.

### Units and jobs

- You usually start with a queen and 3 workers. The queen chamber normally has 7 tiles that serve as both nanitic-worker brood tiles and food storage. You cannot build, delete or upgrade queen tiles.
- The queen only lays eggs. She is immune to disrupting and repositioning effects, and the screen flashes red below 25% health.
- If you have no workers and no food, you get a free nanitic worker to restart the colony.
- Workers do nest jobs in a fixed order: digging, then building, then spawning. Workers in the nest group do any nest job; workers in other pheromone groups only do nearby jobs.
- Soldiers cannot do nest jobs. They fall into six groups: melee, range, tank, medic, harvester and explosive.
- Termite colonies have a king who stays underground near the queen, is invulnerable until the queen dies, and cannot be controlled.
- Job priority: attacking is the highest, then nest work, and gathering food is the lowest.

### Digging

- Black areas are soil you can dig; the rest is indestructible wall. A dug tile must be reachable by workers.
- Tiles have 6 completion points, and worker speed is 2 / 4 / 6 points depending on upgrade level. Up to 2 workers can dig a soil tile at once; the nest entrance allows up to 7 but is the lowest-priority nest job.
- Caverns open all at once when you dig any tile of them, releasing the creatures inside into your nest. Underground marks hint at contents: white silhouettes are small food, red exclamation marks are enemies, green question marks are anything else.

### Building, upgrading and deleting

- Build only in excavated space. Adjacent tiles of the same type form a chamber, and active units from one chamber form a control group.
- Highway tiles cost 5 food and make units 10% / 20% / 25% faster (by level), while moving across any other nest tile is 35% slower.
- Food storage tiles cost 5 food and hold 10 / 40 / 100 food by level. If storage becomes full, the extra food drops on the ground.
- Upgrading is capped at level 3 and costs the same as building. A tile needs 6 upgrade points for level 2 and 12 for level 3. Same-type tiles and highways around it give 1 / 2 / 3 points, walls give 1, and highway tiles give 1 / 2 / 3 to any adjacent tile.
- The most cost-efficient shape for getting every tile to level 3 is a 19-tile hexagon.
- Upgrading heals the units on those tiles and improves their stats and sometimes abilities.
- Deleting first downgrades the tile, refunds 66.67% of the cost as seeds, drops stored food on the ground and kills the matching active units.

### Spawning and population

- Workers carry eggs from the queen to empty brood tiles. Eggs grow into units only while there is enough food, and a brood tile incubates one unit at a time but can hold several active units.
- Population shows as two numbers: active units and the cap set by brood tiles. Worker and soldier populations are counted separately and the queen is excluded.

### Pheromones and control

- You cannot pick individual units. Each chamber is a control group; to split one, delete the tiles between its parts.
- New groups start in the nest group. You have 5 pheromone groups (I to V) and control one at a time.
- Right-click the map or minimap to place a marker. Units walk the shortest path, and 15% stop partway and return to the nest entrance or queen to form a trail. Units that cannot find the way back to the queen die.
- Removing a marker sends its units back to the queen.
- Units respond at 10 units per second regardless of group size, so splitting the same units across several pheromone groups makes them respond faster.
- Toggle icons next to the control panel disable gathering, attacking or mounting. Disabled units still retaliate and finish ongoing fights and carry food they already hold.
- Placing a marker on a nest entrance sends units into that underground area; entrances work like spawners.

### Gathering

- Most species are omnivorous scavengers that eat meat, seeds and sweets. Units automatically haul food in sight to storage, and some move slower while carrying it (encumbered units move 35% slower).
- Small food is carried whole. Large food needs 6 attacks per chunk, can be harvested by several units at once, and progress resets if interrupted.
- Ants are inedible while termites are edible for most omnivorous species. Inedible corpses disappear over time.
- Leafcutter ants and fungus-growing termites use the same rules with leaves and lignocellulose.

### Combat basics

- Units automatically chase and fight enemies they see. Most workers and some soldiers ignore enemies while carrying food.
- Use the information toggles to show tile level and upgrade points, food amounts, and creature health and level.

## Combat, damage and stats

Damage is the single most useful system to understand when picking units, because armour, resistances and piercing can make one unit useless against one enemy and decisive against another. Sources: [Damage Calculation](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Damage_Calculation), [Stat Explanation](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Stat_Explanation) and [Enemy Mounting](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Enemy_Mounting).

### Damage formula

```latex
\text{Damage} = \left[\text{base} \times \text{splash\%} \times (1 - \text{AOE res}) - \text{armour}\right] \times \left(1 - \left|\text{res} - \text{piercing}\right|\right) \times (1 - \text{front res})
```

- Resistance minus piercing cannot go below zero, so piercing only cancels resistance and never makes the target take bonus damage.
- Damage after armour has a floor of 0.5, so even heavy armour never fully blocks a hit.
- Maximum-taken-damage caps are applied last, after the total is calculated.
- Wiki example: 50 physical damage against 20% physical resistance and 10 armour gives (50 - 10) x (1 - 0.2) = 32. If the target caps damage at 5 per hit, it takes 5.
- Every attack is either physical or venom. Only the male scientist, some titans and environmental hazards deal true damage, which ignores all modifiers.
- Attack damage lands instantly; effect damage (poison, burning and so on) is applied separately afterward.

### Damage modifiers a target can have

| Stat | What it does |
| --- | --- |
| Armour | Flat reduction per hit, so it blunts many weak hits far more than a few strong ones |
| Physical / venom resistance | Percentage reduction of that damage type |
| Piercing | Cancels part of the target's resistance |
| Area resistance | Reduces splash damage taken, depending on distance from the main target |
| Front resistance | Reduces damage from frontal attacks |
| Maximum taken damage | Caps damage per attack |
| Evasion | Chance to dodge an attack entirely |

### Abilities and effects

- Abilities always target the nearest valid target and may still fire at targets immune to the effect. Many cannot be used on airborne targets.
- Cooldown, chance, range and attack speed gate usage. Multihit abilities roll their chance separately per hit; multitarget abilities hit each target once. Projectiles do not trigger damage reflection.
- Basic attack is physical, single target, has no cooldown and no effect. Some ant and termite special abilities share its animation, so a unit can look like it is basic attacking while applying a status effect.
- Status effects can stack in three ways: none (duration resets), length stacking (durations add) and value stacking (strength adds while duration keeps counting from the first hit).
- Immunities exist for slow, stun, confusion, fleeing, pickup, knockback and execution. The queen is immune to disrupting and repositioning effects.

### Targeting and threat

- Each hitting attack raises the attacker's threat by 0.1 (some creatures add more), decaying over time. Enemies pick targets among the closest foes, with combat distance equal to hitbox distance divided by the target's threat.
- Practical effect: small, fast creatures are more likely to be retaliated against than big slow ones, and a unit that has been hitting a lot draws attention.
- Smaller creatures can move and attack beneath larger ones, but only a limited number of same-size creatures can fight in one area, so bunching up one size class has diminishing returns.

### Unit sizes (small, medium, large)

- Small: gene-thief, black, wood, fire, little black, Matabele workers, driver ant workers and small soldiers, most worker castes and termite workers.
- Medium: royal guards, leafcutter mediae, army ant majors, big-headed supersoldiers, Matabele medics, termite minor soldiers and similar.
- Large: leafcutter majors, Matabele soldiers, African stink ant soldiers, bullet ant soldiers, termite major soldiers and kings.

### Enemy mounting

- Only colony units can mount, and only on large and huge enemies. Small units can mount large and huge enemies; large units can only mount huge ones. Fungus-growing termite kings, exploding termite kings, bullet ants and the super leafcutter major cannot mount at all.
- Mounting starts only when enough units are attacking. Mounted units can only use basic attack (fire ants are the exception), and non-mounting allies deal 10% more damage to a fully mounted target.
- Mounted units die if the enemy escapes. You can switch mounting off if you would rather your units stay on the ground.
- Mountable huge enemies include adult and uber whip spiders, mantises, scorpions, bullfrogs and centipedes; large ones include tiger beetles, wolf spiders and bombardier beetles (see the wiki page for the full list).

## Playable species

The base game has nine colonies and the DLC adds two more. I opened the pages for the species below; big-headed, little black, driver, army, bullet, stink, slave-maker, trap-jaw and exploding ants are not summarised here, so check their wiki pages ([Eusocial Insects category](https://hoodedhorse.com/wiki/Empires_of_the_Undergrowth/index.php?title=Category:Eusocial_Insects)). Stats are level 1 / 2 / 3 and costs show food with the brood-tile cost in brackets.

| Species | Setting | Defining mechanic | Pre-mission choice |
| --- | --- | --- | --- |
| [Gene-thief ant](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Gene-thief_Ant) | Lab hub | Your customisable story colony; workers plus uncontrollable royal guards | Adaptations bought with Royal Jelly |
| [Black ant](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Black_Ant) | English woodland | Plain biter colony that teaches the basics | None |
| [Wood ant](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Wood_Ant) | French beach | Ranged formic acid shooters | Mortar or rapid-fire shooters |
| [Leafcutter ant](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Leafcutter_Ant) | Ecuador rainforest | Feed on fungus grown from leaves; waste management | Taunt or stun majors |
| [Fire ant](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Fire_Ant) | Green Swamp | Floating bridges across water; venom stings | Pervasive or vigorous soldiers |
| [Matabele ant](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Matabele_Ant) | Ivorian savannah | Eat termites; medics revive dead ants | Anesthetist or fast-responder medics |
| [Fungus-growing termite](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Termite) | Ivorian savannah | Process lignocellulose into fungus; invulnerable king guards queen | None |

### Species notes that change how you play

**Gene-thief ants.** Your story colony. Workers are the shared baseline (health 25 / 35 / 45, cost 20) and the queen has 600 health, 50% physical and venom resistance and takes at most 25 damage per hit. Royal guards (200 health, 10 damage) cannot gather and are uncontrollable. Larry, a secret cheat unit with 100,000 health, is only a joke unit.

**Black ants.** The tutorial species. Soldiers have 50 / 60 / 70 health, armour 0 / 1 / 2, a 40 damage-per-hit cap and 20% area resistance, which makes them good splash-damage tanks early on.

**Wood ants.** Soldiers are sturdy (85 / 100 / 120 health) with 30% area resistance. Shooters are fragile (20 / 25 / 30 health) and only spray while on the ground. Mortar shooters have 500 range, 8 / 10 / 12 venom damage and splash at level 3. Rapid-fire shooters have 400 range, much higher attack speed, and slow enemies by 50% at level 3.

**Leafcutter ants.** Food comes only from fungus.

- Minims are invulnerable and uncontrollable, and each new brood tile gets one free. They haul leaves to brood tiles and carry waste away; fungus grows 1 food per second per brood tile.
- Waste storage dissolves 1 waste every 5 / 4 / 2.5 seconds. Walking on occupied waste storage poisons ants for 60 seconds (30% slower movement, 50% slower attacks, 0.83% health lost per second).
- Waste storage removes upgrade points from adjacent tiles, so do not put it next to chambers you want at level 3.
- Minims panic when the queen takes damage; disable attacking on those groups to keep them working.
- Taunt majors pull aggro and heal, and gain an 80% resistance buff at low health at level 3. Stun majors stun, and at level 3 slow by 90% and add a 30% venom-resistance debuff.

**Fire ants.** Workers can build floating bridges from their own bodies at set points on the bank: place a marker on the far bank to build, and on the near bank to take it down. Bridges collapse when water level changes, and ants caught in the water are washed away. Stings do 10 venom damage while mounting, so fire ants are strong at mounting large enemies. Pervasive soldiers can spawn free after 90 seconds of incubation; vigorous soldiers spawn with +40% speed, +50% damage and resistance buffs for 120 seconds.

**Matabele ants.** Termites are their food; other food only gives 10% of its normal amount, and their harvest of non-termite food is cut to 10%.

- Medics revive dead ants one at a time at the queen. Corpses last 4 minutes; revived ants keep 60% of health and damage, cannot be upgraded, and can only be revived once.
- Soldiers (140 food, 200 / 220 / 300 health) sting for damage over time. Anesthetist medics slow by 60% and stack a physical-resistance debuff up to 100%. Fast-responder medics are quicker at reviving and gain 40% evasion out of combat at level 3.

**Fungus-growing termites.** Minor workers digest lignocellulose (10 per 20 / 15 / 10 seconds) and you lose it if the processor dies. Major workers count toward soldier population and cannot do nest jobs. Minor soldiers cripple with confusion, a 90% slow and up to 60% physical-resistance debuff. Major soldiers add up to +100% attack speed to nearby allies, stacking per hit.

## Royal Jelly, adaptations and status effects

In story mode you customise the gene-thief colony with Royal Jelly (RJ) from the [Formicarium Adaptation](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Formicarium_Adaptation) menu. Status-effect rules come from the [Damage Modifying Effect](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Damage_Modifying_Effect) page.

### How adaptations work

- You start with only level 1 workers. New unit options unlock when you enter a new chapter, and you must pick one of two variants of each unit; that choice is permanent.
- Each unit has four adaptations but you can only have two active. You can swap within a pair by paying the same RJ again.
- Adaptations are abilities, extra effects or stat changes. Adaptations only apply in documentary missions during New Game Plus and in Remix; formicarium challenges always use them.
- Minor improvements convert RJ into improvement points (IP). They are permanent, unavailable during formicarium challenges, and unlock only after you own both adaptations of that unit. The price rises 1.15 times after every trade, separately per unit.
- Hard caps: movement speed 1200, attack speed 500%, maximum taken damage floor of 1, and 80% for piercing and both resistances. Units harvest at most 30 food from large food and 45 from lignocellulose.

### Selected adaptations (RJ cost)

| Unit | Adaptation | Cost | Effect |
| --- | --- | --- | --- |
| Queen | Second wind | 50 | At 75% HP: invulnerable 30 seconds and heals 300 HP; 300-second cooldown |
| Queen | Fierce mother | 50 | At 75% HP: confuses enemies in 2600 radius for 10 seconds |
| Queen | Royal guard | 100 | At 75% HP: 2 royal guards per queen tile for 60 seconds and 5 seconds of free spawning |
| Queen | Royal decree | 100 | At 75% HP: 20 seconds of free spawning without workers or food |
| Worker | Nimble | 30 | +60% out-of-combat evasion; harder to detect |
| Worker | Defensive | 30 | Damage cap 20 per hit, +20% physical and venom resistance |
| Worker | Efficient brood | 40 | +40 speed, +10 harvest, +2 job speed, no nest-tile speed penalty |
| Black ant soldier | Meat wall | 50 | +50% physical resistance |
| Wood ant shooter | Crippling | 100 | Targets take 40% more physical damage, stacking to +100% |
| Wood ant shooter | Weakening | 100 | Targets take 40% more venom damage, stacking to +100% |
| Leafcutter major | Resilient | 200 | Nearby allies gain +30% physical and venom resistance |
| Fire ant soldier | Evasive | 200 | +30% evasion |
| Matabele medic | Sustain | 400 | Attacks heal nearby allies for 3 HP per hit |
| Matabele medic | Surgeon | 600 | Revived ants keep 85% health and damage |
| Exploding ant minor soldier | Chain reaction | 600 | Explosions boost nearby exploders by 20%, stacking |

Unit unlock prices (level 1) include black ant soldier 75, wood ant shooter 150, leafcutter major 300, fire ant soldier 500, Matabele medic 800 and bullet ant soldier (level 3) 2000.

### Status effect rules

- Buffs apply to the user, debuffs to enemies. Identical effects can be applied repeatedly but do not stack in value, except Weakening, Crippling and damage flash buffs.
- Resistance debuffs cap at 100%, and resistance changes apply after the resistance-minus-piercing step. General damage buffs and armour buffs apply before the damage formula.
- Wiki example: 10 physical damage with 20% piercing against 10% physical resistance, 1 armour, a -30% resistance debuff and +2 armour gives about 9.1 damage.
- Invincible units cannot be targeted at all: leafcutter minims, colony termite kings, assassin bugs and queens during Second wind.
- Physical resistance debuffers include anesthetist Matabele medics, termite minor soldiers and little black ant soldiers. Venom resistance debuffers include stun leafcutter majors.

## Enemies, AI colonies and custom games

Sources: [Swarm and Colony](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Swarm_and_Colony), [Custom Game Mode](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Custom_Game_Mode) and [Paid Extra Content](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Paid_Extra_Content).

### Swarm creatures

- Swarm creatures are anything from spawners or underground caverns. Cavern creatures are fixed at mission start and never respawn. Surface creatures are driven by a patrol system, and nocturnal or diurnal species only appear at their time of day in documentary missions and custom games.
- Hidden cavern creatures show as symbols on the soil, and the symbol size hints at their strength. Hidden creatures can tunnel through soil and link caverns, so digging into one tunnel can open several caverns at once and flood your nest.
- Some cavern creatures dig inside your nest or break indestructible walls to reach your queen or release more creatures. Aggressive ones head straight for the queen; friendly ones wander.
- Swarm ants and termites can be enemies or allies in special missions. Their queens can move but cannot lay eggs, and their workers cannot gather aphids, mount or build bridges.
- Powerscaling multiplies stats by star level X: health, damage and effect value by (X + 1)^2 x 0.1 + 0.9, and reflection and knockback by (X + 1)^2 x 0.01 + 0.99. Powerscaled creatures are at most three times normal size. A star icon shows the level, with a plus above 13.
- Powerscaled enemies appear in Babysitting, Occupation, Adventure, Occupation 2 and Festive Spider, and in New Game Plus.

### Computer-controlled colonies

- AI colonies play by the same rules and are eliminated when their queen dies. Their tiles are deleted every 0.5 seconds, refunding 66.67% of cost as a reward for the victor (dead larvae, termites, leaves or lignocellulose, depending on your species).
- Their nests are pre-designed hexagon chambers with no highways, and nanitic workers always stay inside to do nest jobs.
- AI behaviour varies by mission: none (follows scripts), old system (checks fixed locations) or new system (scans territory continuously for food and danger). AI colonies control up to 3 pheromone groups.
- Gathering groups fight on the way, and retreat after enough casualties. Attacking groups, made only of large soldiers where castes differ, are used to invade your nest or protect gatherers.
- The wiki notes that AI colonies need a head start and the occasional free food or respawn to stay threatening. They also respond to your most recent surface pheromone markers when the group is large enough to be detected.

### Custom game (freeplay)

- Pick a premade map (The Dunes, Towhead, Embankment, Basin, Sandspit, Imprisoned, Strawclutch, Grasslands, Drive Them Back, Causeway, Creek), time of day, day-night cycle and fog of war.
- Victory conditions: none, conquest, domination, survival, besieged, hunter, biomass or score, with an adjustable threshold.
- Environmental difficulty runs from easy to impossible and can be constant, ramp, spikes, ramp with spikes, scale with colony, or random. You can also set spawn rate, grace period, nest invasions, attack waves (first wave defaults to 720 seconds), uber creatures and landmarks.
- Each colony can be player or AI, with species, colour, team (0 to 5), AI difficulty, temperament (docile to aggressive), reaction speed and cheat level (never, headstart, underhanded, cheater, crooked, corrupt).
- Custom colonies let you choose soldier variants and add up to 200 improvement points per stat. Story colonies can be imported.
- Settings are saved as editable CSV files you can share, and games can be saved or autosaved. Five sample scenarios ship with the game (Bad Neighbors, Hunt the Ubers, Pot Luck, Waves from Hell, You vs the World).
- Skirmish is the quick mode: conquest victory, medium difficulty ramping from 10%, nest invasions and upkeep on, no waves or ubers, and no fog of war.

### DLC

- Supporter's Pack: alternate Myrmecia ereptor skin for gene-thief ants, a sound widget with 37 music tracks, wallpapers, portraits and emojis. It is cosmetic.
- Exploding Species DLC: adds exploding ant and exploding termite colonies and the missions Firebreak and No Ant's Land. Exploding major soldiers and termite soldiers unlock in story mode only after The REAL Final Experiment.

## Tips to play better

The wiki documents mechanics rather than strategy, so each tip below is tagged. **\[Wiki\]** means the rule is stated on the wiki and the advice follows directly. **\[Inference\]** means it is my reading of those rules and not wiki advice, so test it in an easy mission before relying on it.

### Opening and economy

1. **\[Wiki\]** Dig and build first, spawn second. Nest jobs run in the order dig, build, spawn, and workers in the nest group do all of them, so keep enough workers at home before sending anyone out.
2. **\[Wiki\]** Treat food as finite. On most difficulties corpses do not rot and plants do not regrow, so waste nothing, and expect easy mode to double food from kills.
3. **\[Wiki\]** Gathering is the lowest-priority job and attacking the highest. If an expedition is losing workers to fights, disable attacking on that group.
4. **\[Wiki\]** Build highways between brood, storage and the entrance. Non-highway nest tiles slow units by 35%, and a highway also gives upgrade points to adjacent tiles.
5. **\[Wiki\]** Plan chambers for upgrades before building. Level 2 needs 6 points and level 3 needs 12, same-type neighbours give points, and the 19-tile hexagon is the most efficient shape to reach level 3 everywhere.
6. **\[Inference\]** Upgrade cost equals build cost and upgrading heals units, so the cheapest big army boost is usually upgrading existing brood tiles rather than spamming new low-level ones, if your population cap allows it.
7. **\[Wiki\]** Mind the population cap. It is set by brood tile count, and workers and soldiers are capped separately, so build the right mix of tiles for each.
8. **\[Wiki\]** Dig the entrance and caverns deliberately. Opening one cavern releases the whole connected tunnel system into your nest, so make sure soldiers are ready first and read the cavern marks (red exclamation means enemies).

### Pheromones and army control

1. **\[Wiki\]** Use all five pheromone groups. Responding speed is a fixed 10 units per second, so splitting units across groups gets them moving sooner.
2. **\[Wiki\]** Keep one group on the nest. Removing a marker sends units home, and units that cannot find a path back to the queen die, so do not strand groups across blocked routes or rising water.
3. **\[Wiki\]** Place a marker on a nest entrance to send units underground, which is how you clear caverns and defend deep tunnels.
4. **\[Wiki\]** Split brood chambers by deleting tiles between them if you need separate control groups, for example a medic chamber apart from a tank chamber.
5. **\[Inference\]** Send soldiers and workers on different groups so you can toggle gathering or attacking on one without freezing the other.

### Fighting well

1. **\[Wiki\]** Match damage type to the target. The formula subtracts flat armour first and then applies resistance minus piercing, so many weak hits are poor against high armour, while piercing is wasted on a target with no resistance.
2. **\[Wiki\]** Use debuffers early. Resistance debuffs (anesthetist medics, termite minor soldiers, wood ant Crippling and Weakening) multiply the damage of everything else on the target.
3. **\[Wiki\]** Mount big enemies with small units. Fire ants gain a 10 damage sting while mounted, and non-mounting allies deal 10% more damage to a fully mounted target.
4. **\[Wiki\]** Expect small, fast units to draw retaliation more than large slow ones, because enemies divide distance by threat. Put tanks and taunt majors forward to hold attention.
5. **\[Wiki\]** Fight near your queen if you are outmatched. The queen is immune to stun, confusion, knockback and pickup, and takes at most 25 damage per hit, but she has finite health and her death loses the mission.
6. **\[Inference\]** Use the red screen flash at 25% queen health as a last-resort cue; if you see it, you have already waited too long to pull defenders back.
7. **\[Wiki\]** Use Battle Arena and the Custom game to learn matchups without risking a campaign. It uses story-mode stats, so results carry over to story missions.

### Species-specific advice

- **Leafcutters \[Wiki\]:** keep waste storage away from chambers you want to upgrade, and keep a stream of minims working by disabling attacking on minim groups when the queen is under attack.
- **Fire ants \[Wiki\]:** plan bridges around water level changes, and never delete tiles that bridge-building ants belong to, or the bridge collapses.
- **Matabele ants \[Wiki\]:** feed on termites, not other food. Keep medics alive since corpses only last 4 minutes, and remember that revived ants cannot be revived again.
- **Termites \[Wiki\]:** protect minor workers, because losing a processing worker loses the lignocellulose inside it.
- **Wood ants \[Inference\]:** shooters have only 20 to 30 health, so screen them with sturdy soldiers rather than letting them lead.

### Using adaptations (Royal Jelly)

1. **\[Wiki\]** Pick your variants and adaptations with the missions in mind; swapping within a pair costs the same RJ again, but variant choices are permanent.
2. **\[Wiki\]** Spend RJ on adaptations before minor improvements, since improvements unlock only after both adaptations are owned and cost 1.15 times more after every trade.
3. **\[Inference\]** Queen adaptations are cheap (50 to 100 RJ) and trigger at 75% health, so Second wind or Royal decree are efficient insurance for hard missions.
4. **\[Wiki\]** Remember adaptations are off in documentary missions on your first story run but on in New Game Plus, so expect those missions to feel easier the second time.

### Common mistakes to avoid

- Deleting tiles while units are active on them, which kills the units and drops the stored food on the ground.
- Letting a storage tile fill up unexpectedly; the overflow lands on the ground.
- Starting a New Game Plus without being ready; it cannot be undone and raises difficulty.
- Forgetting that you cannot save mid-mission in story or arcade missions.
- Relying on the inspect tool for speed: the wiki says it shows only 10% of the real movement speed value, and it cannot show ability stats beyond basic attack.

### Open questions

- The wiki does not give a stated splash-falloff formula, so area damage with partial falloff is unknown.
- I did not open the environment, creature, titan or mission walkthrough pages, so enemy weaknesses and per-mission strategy are not covered. I can add those if you want.

### Sources

All pages opened on 15 November 2026 from the [Empires of the Undergrowth Official Wiki](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Main_Page): [Basic Mechanics](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Basic_Mechanics), [User Interface](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/User_Interface), [Damage Calculation](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Damage_Calculation), [Stat Explanation](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Stat_Explanation), [Enemy Mounting](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Enemy_Mounting), [Swarm and Colony](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Swarm_and_Colony), [Mission Difficulty Setting](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Mission_Difficulty_Setting), [Story Mode](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Story_Mode), [Arcade Mode](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Arcade_Mode), [Custom Game Mode](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Custom_Game_Mode), [Paid Extra Content](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Paid_Extra_Content), [Formicarium Adaptation](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Formicarium_Adaptation), [Damage Modifying Effect](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Damage_Modifying_Effect), and the species pages for [Gene-thief](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Gene-thief_Ant), [Black](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Black_Ant), [Wood](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Wood_Ant), [Leafcutter](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Leafcutter_Ant), [Fire](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Fire_Ant), [Matabele](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Matabele_Ant) and [Termite](https://wiki.hoodedhorse.com/Empires_of_the_Undergrowth/Termite).
