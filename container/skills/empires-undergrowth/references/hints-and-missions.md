<!-- Source: George's compiled guide from the older fan wiki (moved to the official wiki in mid-2024), read 15 Nov 2026. Has the mission-by-mission notes. Numbers may be out of date: check them against mechanics-strategy.md. -->

# Empires of the Undergrowth: Gameplay Hints & Tips Guide


## Overview

Empires of the Undergrowth is a real-time ant colony game by Slug Disco Studios: you dig a nest, build chambers, raise brood and send ants out to gather food and fight. This guide collects the gameplay hints from the fan wiki's mechanics pages. The wiki says it is outdated and has moved to the official Hooded Horse wiki, so treat numbers as a guide and check them against the current game.

The core loop is simple. Workers dig and build underground, gather food on the surface, and feed the queen's eggs. Soldiers split into melee, range, tank and medic groups and defend or attack. You lose when the queen dies, so everything else serves her survival.

## Early game and nest setup

You usually start with a queen and 3 active workers, plus 7 free nanitic workers. The wiki's setup hints:

- **Protect the queen first.** The screen flashes red below 25% queen health. She is immune to disrupting and repositioning effects but cannot lay anything except eggs.
- **Nanitic workers are a safety net.** If you have no workers and no food, one spawns for free to restart the colony.
- **Nest jobs run in a fixed order:** digging, then building, then spawning. Workers in the nest group do them automatically; workers in other pheromone groups only do nearby jobs and ignore resources and enemies while on nest jobs.
- **Dig deliberately.** You can only dig in the black area. Up to 2 workers dig a tile at once; the nest entrance takes up to 7 and is always dug last.
- **Read the underground marks before digging.** Green question marks are allies or docile creatures, red exclamation marks are aggressive enemies, and bigger marks mean stronger creatures. A cavern is fully excavated the moment you break in, and aggressive enemies head straight for your queen.
- **Build highways early.** Ants move 10%, 20% or 25% faster on highway tiles (by level) and 50% slower on other nest tiles. A highway tile costs 5 food.
- **Plan chambers for upgrades.** Level 2 needs 6 upgrade points and level 3 needs 12. A 19-tile hexagon is the most cost-efficient shape that lets every tile reach level 3.
- **Deleting refunds 66% of the cost** as seeds, but the matching active ants die and food is left on the ground.

## Economy, food and controlling your ants

Food is the only thing that turns eggs into ants and builds tiles, so the wiki's hints centre on keeping it flowing.

- **Eggs only grow with food.** Workers carry eggs from the queen to empty brood tiles, and a brood tile holds one ant at a time. Larvae stop growing midway if the food runs out.
- **Watch both population numbers.** The left number is active ants, the right is the cap set by your brood tiles. Workers and soldiers have separate caps, and the queen is not counted.
- **Build storage before you need it.** A food storage tile costs 5 food and holds 10, 40 or 100 food at levels 1 to 3. If storage is full, carried food is dropped on the ground.
- **Large food is a team job.** Big items must be taken apart and several ants can harvest at once, each cutting a limited amount per trip. Small food is carried off whole. Enemy ants cannot be eaten, but other dead creatures can.
- **Turn on resource information** to see food amount and harvest capacity before sending a group.
- **Use pheromone groups.** You get a nest group plus five groups (I to V). Right-click the map or minimap to place a marker; ants follow it in a trail, and a small share will turn back on the way. You never control single ants.
- **Control groups follow chambers.** Ants from one brood chamber form one group. To split a group, delete the tiles between the brood chambers.
- **Beware of stranding.** Ants that cannot find their way back to the queen die. Nest entrances teleport ants between surface and underground, and you can place a marker on an entrance to send them through.
- **Use the toggles.** You can disable gathering, attacking or mounting for a group. Ants still return carried food and still retaliate when hit.
- **Leafcutter missions add resources.** You also manage leaves and waste, each with its own storage tile, and brood capacity shows food in green and waste in red.

## Combat, damage and mounting

Soldiers come in four roles: melee (red sword), ranged (yellow target), tank (blue shield) and medic (purple cross). Workers can fight too, but they can ignore enemies while carrying food.

- **Ants auto-engage.** They follow and attack anything in sight. With attacking disabled they still retaliate and must finish ongoing fights.
- **Use tanks to hold aggro.** Each hit adds stackable threat, and the highest-threat attacker is most likely to be targeted. Tanks generate extra threat on top of the base 0.1.
- **Space matters.** Only so many creatures fit in a fight, and small ones can fight beneath larger ones. A unit with no reachable target moves to find a better position.
- **Upgrades heal.** Upgrading a tile instantly heals its ants and improves their stats; downgrading by deletion also heals them.
- **Turn on unit information** to see health bars, ant levels (yellow diamonds) and creature ranks (yellow stars).

### Damage formula

```latex
\text{Damage} = [\text{base} \times \text{splash} \times (1 - \text{AOE res}) - \text{armor}] \times (1 - [\text{resistance} - \text{piercing}])
```

Armor cuts damage by a flat amount, with a floor of 0.5 per hit. Physical and venom resistance cut damage by a percentage, and piercing reduces that resistance. Damage-over-time ticks count as separate attacks, so a creature with a per-hit damage cap limits each tick. Only the male scientist and fungus waste poisoning are confirmed to deal true damage that ignores all of this. AOE resistance applies when a creature is more than 10 units from the main target.

### Mounting large enemies

- Only colony ants can mount large and huge creatures, and only a percentage of fighting ants can climb at once.
- Small ants can mount large and huge enemies. Medium and large ants (leafcutter mediae and majors, matabele soldiers, army ant majors) can only mount huge ones. Super leafcutter majors cannot mount.
- Mounted ants use only basic attacks (fire ants are the exception) and can still be hit by damage reflection.
- Large creatures take extra damage when enough ants are mounted. The wiki does not say how much.
- Mounted ants are lost if the creature leaves the map. Disable mounting to make ants dismount.

## Missions, difficulty and enemy colonies

The wiki recommends medium difficulty for a first playthrough. Missions run on easy, medium, hard, extreme or impossible, and a few have a single fixed difficulty.

- **Higher difficulty changes more than health.** Resources are scarcer, swarms are bigger with larger variants appearing earlier, attack waves come sooner and more often, titans are bigger and tougher, and enemy colonies are more aggressive and cheat more.
- **Easy halves enemy health** and doubles the food they drop. Some missions add unique enemies on impossible.
- **You cannot save mid-mission** in story missions. Freeplay can be saved, because it has no scripting.
- **Know the win condition.** You must finish every objective. For a survival timer you only need the queen alive at the end; for attack waves you must eliminate all active wave enemies.
- **Let others do the killing.** Mutual enemies and environmental hazards count toward eliminations.
- **Original resources only.** If an objective needs gathering from specific locations, your own refunds and enemy leftovers usually do not count.
- **Achievements are optional.** They exist for replay value on story and holiday missions and do not affect rewards. Enable achievement tracking to see whether you are meeting them.

### Enemy colonies (AI)

- AI colonies use the same rules as you but are less responsive, so they get a head start and cheat to stay threatening.
- They cannot invade your nest in missions, but can in freeplay. Other wild enemies are hostile to them.
- A defeated AI colony turns into food: its tiles are deleted every 0.5 seconds, refunding 66% of the building cost.
- Newer AI behaviour (Cold Blood, A Bridge Too Far, and freeplay) scouts constantly, retreats after casualties and returns once danger passes. It ignores your pheromone markers. Older behaviour (The Harvest, Possibly the Final Experiment) tracks your most recent marker or invades your nest.
- AI colonies only build hexagon chambers and no highways, so they move slowly inside their own nests.

### Freeplay

Freeplay lets you tune colonies, environmental difficulty, victory conditions and maps, and save your settings. You can bring story-mode colonies into freeplay, and later story saves do not alter them.

## Mission guides

The wiki has no step-by-step walkthroughs, so these guides pull each mission's objectives, rules, enemy waves and achievements from its page. Rewards are 4 to 6 territory plus food and Royal Jelly, scaled by difficulty (230% to 420%), with a +250% first-clear bonus (+1100% for The Harvest) and +100% for challenge mode. Documentary missions ignore your formicarium customisations.

### 1. New Home (black ants, English log, no surface)

- **Objective:** eliminate all enemies.
- **Setup:** woodworms, woodlice and devil's coach horse beetles live in your nest. All enemies are on the same side. On impossible the 2 central caverns hold exactly 10 woodlice each.
- **Hint:** dig toward weak creatures first and watch the underground marks, since breaking into a cavern releases everything at once.
- **Challenge mode:** mole crickets arrive after 4 minutes, drawn to larger chambers (dust clouds warn you). Waves go 1, 2, 1, 3, 1, 4 crickets, with the gap shrinking 10 seconds per wave down to 80 seconds. Keep chambers small to blunt them.
- **Achievements:** no soldier upgrades (medium); win within 17 minutes (hard); keep enemies 3 tiles from the queen (extreme); excavate 10 woodlice last (impossible); win before 10 crickets attack, or after 50 (challenge).

### 2. Subjugation (black ants, English log, no surface)

- **Objectives:** build or upgrade 50 worker tiles and 50 soldier tiles, then survive the final wave.
- **Setup:** slave-maker raids begin only after you kill a funnel-web spider. Wave 1 is one unstoppable stealer; later waves arrive every 100 seconds, growing in number and level. Soldiers go for your queen while stealers wander looking for larvae.
- **Hint:** if both tile objectives are done when a wave is about to arrive, that wave becomes the final one, so finish them early. Guard your larvae.
- **Achievements:** win in 16 minutes (medium); kill 10 funnel-web spiders in 6 minutes (hard); lose 80% of larvae to one wave (extreme); lose only one larva (impossible); get a mole cricket to kill a funnel-web spider (challenge).

### 3. Rising Tide (wood ants, French beach, surface)

- **Objective:** survive 3 nights.
- **Setup:** pick mortar or rapid-fire shooters before starting. You begin with 4 black ant workers. Water rises every 75 seconds in the evening, washing away creatures, and recedes in the morning leaving sand fleas. A fish washes up on day 2.
- **Waves (100 seconds apart):** night 1 is three hermit crab waves; night 2 is three sand bear wolf spider waves; night 3 is spiders, then crabs, then large spiders plus many tiny ones. On impossible a huge sand bear wolf spider hides on layer 4.
- **Hint:** the enemy only invades when attacked (large hermit crabs excepted), and nearby enemies are drawn to a fight every 5 seconds, so pick battles carefully.
- **Achievements:** leave the fish unharvested (medium); never let enemies enter the nest (hard); kill 2 dune tiger beetles before night 1 (extreme); kill the huge spider (impossible); build no worker tiles (challenge).

### 4. Queen of the Hill (wood ants, French beach, 2 AI colonies)

- **Objective:** survive 4 days. You cannot continue after victory.
- **Setup:** a black ant colony and a wood ant colony are allied against you. Their waves spawn free during the day, 70 seconds apart, alternating black ants and wood ants, with a mixed final wave carrying both queens. On night 4 both nests flood.
- **Resources:** 2 aphid farms are yours; the fish on layer 3 is reachable only on days 1 and 2.
- **Hint:** the wiki notes you can disable attacking to keep the migrating queens alive beside yours; they still die by the end.
- **Achievements:** kill 2 ladybirds from different farms within 30 seconds (medium); gather 100 food from the fish (hard); no melee tiles (extreme); no shooter upgrades (impossible); kill 3 large hermit crabs (impossible challenge).

### 5. The Harvest (leafcutter ants, Ecuadorian rainforest, 1 AI colony)

- **Objectives:** build 5 leaf storage and 5 refuse storage tiles, turn one leaf into fungus, then gather 10,000 leaves (up to 14,000 on impossible) before the enemy or kill the enemy queen.
- **Setup:** pick taunt or stun majors. The rival gathers at random spots and retreats after casualties, returning about 60 seconds later with attackers that follow your latest marker. Its waves, stun majors only, start once you pass 9,000 leaves while ahead, every 2 minutes.
- **Hint:** only leaves from the surface count, and the forest holds 34,455 food of saplings. Defend the gathering lines, because surface enemies mostly roam your side of the map.
- **Challenge mode:** phorid flies appear every 6 minutes 30 seconds.
- **Achievements:** kill the enemy queen (medium); win before the rival has 5,000 leaves (hard); no digging out underground enemies (extreme); win within 43 minutes (impossible); lose no ants to flies (challenge).

### 6. Front Line (leafcutter ants, Ecuadorian rainforest, army ants)

- **Objective:** push the army ants back. You win when their progress bar is fully depleted.
- **Setup:** the mission starts at night with your nest entrance already open, 7 extra minor tiles and 7 media tiles. Pick taunt or stun majors first.
- **How the bar works:** it creeps toward your nest over time regardless of army ant numbers, even at night. Army ants advance a lane each time it passes a threshold and retreat when it drops. Only killing army ants pushes it back.
- **Hint:** scouting groups of mediae run back to call reinforcements if they spot you. Reinforcements do not move the bar. A huge whip spider hides under a log mid-map by day and emerges at night (from the 4th night on easy to hard, the 3rd on extreme, the 1st on impossible).
- **Achievements:** win before night 2 (medium); stop scouts reporting back (hard); build no major tiles (extreme); kill the huge whip spider before day 3 (impossible); no level 3 ants (challenge); gather every leaf (impossible challenge).

### 7. Cold Blood (fire ants, Green Swamp Preserve, 2 AI colonies)

- **Objectives:** eliminate the bullfrog, then survive the final invaders.
- **Setup:** pick pervasive or vigorous soldiers. You get a milkweed plant with 3 aphids. The bullfrog starts at one sixth health and regains it by eating small amphibians from nearby spawners. If it drops to 25% health and you do not kill it within 30 seconds it leaps off the map.
- **Final phase:** 60 seconds after the bullfrog is gone, toads and salamanders enter your nest via the hillside. Survive 2 minutes and clear every active enemy.
- **Enemy colonies:** the little black ants get free food every 60 seconds and take your aphids or invade from day 3 (day 1 on impossible). The big-headed ants take your aphids from day 4 and only invade once supersoldiers unlock after you attack them. Attacking either colony first brings them to you sooner.
- **Hazards:** green lynx spiders on pitcher plants kill climbing ants, and wasp mantidflies heal on the plants.
- **Achievements:** do not kill the enemy queens (medium); dig out all underground food before night 2 (hard); kill both queens (extreme); engage both colonies in the first 5 minutes (impossible).

### 8. A Bridge Too Far (fire ants, rising flood, 1 AI colony)

- **Objectives:** reach a population score (195 on easy up to 480 on impossible, workers 1 point and soldiers 1.5), and gather 50 to 125 ants at the top of the mound.
- **Setup:** water rises each morning and evening and never recedes. You can build up to 19 bridges (1, 2, 1, 5, 2, 6, 2 from layer 9 down to layer 3) to reach resources and aphids. There are 50 aphids on the map. You cannot continue after victory.
- **Hint:** surface enemies washed ashore invade 60 seconds before the water rises. The great blue skimmer drops to layer 3 at 55% health and flies away unless you mount it within 30 seconds.
- **Enemy colony:** the little black ants are stuck on the southwest island, reachable only on nights 2 and 3, and flooded from day 4.
- **Achievements:** gather all aphids (medium); gather none (hard); let 14 completed bridges be flooded (extreme); clear the northwest island and kill the little black queen the same day (impossible).

### 9. Triage (Matabele ants, Ivorian savannah, 3 termite colonies)

- **Objective:** survive 3 nights. Pick anesthetist or fast-responder medics first. The wiki lists no rewards or achievements for it yet.
- **Food source:** three termite colonies (north, northwest, northeast) are your main food, active only at dawn and dusk. Raiding one puts its chambers on cooldown, so rotate between colonies. Killing a termite queen ends that colony and yields 1,500 food.
- **Threats:** earwigs, alligator-back scorpions and juvenile sun spiders at night. An adult sun spider breaks into the nest on night 2, an adult African centipede on night 3 and an adult emperor scorpion on the last night.

### Formicarium challenges (story spoilers)

These gate story progress and run in your own formicarium with your customisations applied. If you fail, you restart from just before the attempt. Rewards (base 6 to 8 territory, 475 to 650 food, difficulty bonus 480% to 1,120%) are only paid on the first clear. Your brood tile cap before each challenge is 100, 125, 150 and 175 in order.

**The First Experiment (survive waves from 2 directions).** Eight waves via the feeding tubes: 10 and 20 black ants, then 40, 50 and 60 gene-thief ants, a break, 20+20 then 30+30 black and gene-thief ants, a break, then a large mixed final wave with devil's coach horse beetles dropped in (edible). Each wave starts only once the last is dealt with, and you get food during breaks. Achievement Vanilla: win without unlocking black ant soldiers.

**The Second Experiment (3 directions).** Seven waves: 20 black ants, then 20, 40 and 50 wood ants, a break, 30 black + 30 wood, then 30 black + 30 wood + 30 gene-thief, a break, and a large mixed final wave with beach tiger beetles and wolf spiders dropped in. Achievement No Entry: never let enemies into your nest.

**Possibly the Final Experiment (defeat the counterpart colony).**

- The goal is to kill the enemy queen. Your formicarium connects to theirs by a glass tube, and the safe zone runs from your surface entrance to the halfway point.
- Their army is 22 gene-thief workers, 74 slave-maker soldiers, 57 trap-jaw soldiers, 66 army ant mediae and 40 army ant majors. They wait at their entrance and only advance when you move ants out of the safe zone, then follow your latest marker. They retreat after heavy losses.
- If you hole up underground with no soldiers, they invade at once. If you invade their nest, they hold their soldiers at the entrance until your invaders are dead.
- The male scientist interferes: he crushes ants fighting in the enemy formicarium with his finger (not once you are in their nest), knocks on the glass to stun and damage ants if you keep soldiers in your nest, and drops inedible beetles and whip spiders in to force you out. If you fight outside, he sometimes drops edible mantises or mole crickets to even things up.
- Achievement Fool's checkmate: place a single pheromone marker and never move ants between groups. Beating the other side, The Other Foot, unlocks the counterpart colony for freeplay.

**The Final Experiment (eliminate the hybrids in time).** Three waves, each starting after the last is cleared: hermit scorpion, then whip mantis and praying spider, then dragantula. Keep soldiers on the surface or the scientist stuns your ants, and if you take too long he knocks hard enough to kill your queen. His dialogue gives hints: mounting the hermit scorpion makes it break its shell earlier, the twins fight each other for a while before separating, and the dragantula must focus briefly before its aerial attacks. Achievement Clever Little Ants: lose no ants to the dragantula's charge. Hybrids give only 14% of their food on replays.

*Not covered:* the wiki also lists Drive Them Back and Last Mound Standing (the Matabele and termite chapter) but this guide does not include them.

## Quick reference and sources

| Topic | Number to remember |
| --- | --- |
| Starting force | Queen, 3 workers, 7 nanitic workers |
| Queen danger warning | Below 25% health |
| Highway tile | 5 food; +10/20/25% speed by level |
| Off-highway nest tiles | 50% slower |
| Food storage tile | 5 food; holds 10/40/100 |
| Upgrade points | 6 for level 2, 12 for level 3 |
| Best upgrade chamber | 19-tile hexagon |
| Delete refund | 66% of cost |
| Pheromone groups | 5 (I to V) plus nest group |
| Workers per dig tile | 2 (entrance: 7) |
| Armor floor | 0.5 damage per hit |
| Gene-thief worker speed | 300 units per second |

Page text read on 2026-11-15 from the fan wiki, which says it moved to the official Hooded Horse wiki in mid-2024. Some mechanics, such as mounting bonus damage and splash falloff, are listed there as not revealed.

**Sources**

- [Basic Mechanics](https://empires-of-the-undergrowth.fandom.com/wiki/Basic_Mechanics)
- [Damage Calculation](https://empires-of-the-undergrowth.fandom.com/wiki/Damage_Calculation)
- [Enemy Mounting](https://empires-of-the-undergrowth.fandom.com/wiki/Enemy_Mounting)
- [Difficulty](https://empires-of-the-undergrowth.fandom.com/wiki/Difficulty)
- [Stat](https://empires-of-the-undergrowth.fandom.com/wiki/Stat)
- [AI Colony](https://empires-of-the-undergrowth.fandom.com/wiki/AI_Colony)
- [User Interface](https://empires-of-the-undergrowth.fandom.com/wiki/User_Interface)
- [Freeplay Mode](https://empires-of-the-undergrowth.fandom.com/wiki/Freeplay_Mode)
- [Frequently Asked Questions](https://empires-of-the-undergrowth.fandom.com/wiki/Frequently_Asked_Questions)
