"""Build Version 3 dataset (threaded multi-turn tutoring), from the 32 hand-written cards.

Run (after generate_dataset.py, validate_split.py, build_v2.py):  python build_v3.py
Outputs: data_v3/train|val|test.jsonl, data_v3/instructor_review_v3.csv, data_v3/cards_for_review.csv

Design (from tester feedback on v1/v2):
  * every tutor reply after turn 1 quotes what the student just said (keeps the thread)
  * regulation is raised only when the student asks (or in the dedicated 'legal' flow)
  * student can refuse a topic ('no regulations'), state an early choice, get stuck, change an assumption
  * no numbers/shelf-life claims the student did not give
  * replies are short and specific (risks, option trade-offs from the card)
Same test/val CARD groups as v2, so v2 and v3 are comparable on unseen products.
"""
import csv, json, os, random, re, collections
from cards import CARDS
from extras_v2 import SCOPE_TOPICS, DECLINE_OPEN, CONCEPTS
from extras_v3 import REDIRECT_V3, NEW_SCOPE_TOPICS, REVISIT, CHANGES, LEGAL_FOLLOW
from generate_dataset import SYSTEM, msgs

rng = random.Random(2027)
low = lambda s: s[0].lower() + s[1:]
q = lambda s: '"' + s.strip().rstrip(".!") + '"'
EPA_TXT = "your Metropolitan/Municipal Assembly and the Environmental Protection Agency"

def join(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]

def regshort(c):
    seen = []
    for r in c["reg"]:
        s = re.sub(r"\s*\([^)]*\)", "", r).strip()
        if s not in seen:
            seen.append(s)
    return join(seen)

def opt(c, name): return next(o for o in c["opts"] if o[0] == name)
def cheapest_other(c):
    others = [o for o in c["opts"] if o[0] != c["best"]]
    return ([o for o in others if o[3] == "low"] or others)[0]
def names(c, k):
    n = [o[0] for o in c["opts"]]; k %= len(n)
    return join(n[k:] + n[:k])

def head(sent):
    """Short echo of a student sentence: the part before the first comma if it is long enough."""
    first = sent.split(",")[0]
    return first if len(first.split()) >= 3 else sent
def risk1(c): return c["risk"].split(",")[0].split(" and ")[0]
JUDGE = ["Judge each on protection, local availability, cost tier and what happens after use.",
         "Check each first against {r1}, then on local availability, cost tier and end-of-life.",
         "Compare them on protection, cost tier, local availability and what happens after use, starting with {r1}."]
ASK = ["Which would you choose? Give one advantage and one drawback.",
       "Which one would you pick, and why? Name one advantage and one drawback.",
       "Which do you choose? Tell me one advantage and one drawback."]

OPENERS = ["", "", "Hello. ", "Good day. ", "Hi, I need help. "]
OPEN = ["Good place to start.", "Thanks for the details.", "Happy to guide you through this.",
        "Good problem to work on.", "This is a real-world case, so let's treat it that way."]
PRAISE = ["Good thinking.", "That's a fair start.", "Good, you gave a reason, not just a name.", "Nice, you weighed both sides."]
CH = ["I think the {n}. Advantage: {a}. Drawback: {d}.",
      "I would choose the {n}. Advantage: {a}. Drawback: {d}.",
      "My pick is the {n}. Good point: {a}. Weak point: {d}."]
EARLY = [" I've already chosen the {n}.", " I have already decided on the {n}.", " My mind is made up: the {n}."]
NOREG = ["Please don't talk about regulations, I only want help choosing a material.",
         "I'm not asking about regulations, just the material.",
         "No regulations for now, please. Help me choose the material."]
STUCK = ["I don't know where to start.", "No idea. Can you give me a hint?", "I'm stuck."]
DEMAND = ["Just tell me the answer.", "Give me the final answer please.", "I only need the answer."]

def first_reply(c, k):
    o = OPEN[k % 5]; f = k % 3
    if f == 0:
        return (f"{o} For {c['product']}, the main things to watch are {c['risk']}. Before we compare materials, "
                f"I need two things. {c['q1']} And {low(c['q2'])}")
    if f == 1:
        return f"{o} I need two facts first. {c['q1']} Also, {low(c['q2'])} Then we'll compare options together."
    return (f"{o} Let's take it step by step. For {c['producer']}'s {c['product']}, the risks are {c['risk']}. "
            f"{c['q1']} And {low(c['q2'])}")

def cand_reply(c, k):
    return (f"Thanks. With {q(c['a2'])} in mind, the main risks are {c['risk']}. "
            f"Candidates: {names(c, k)}. {JUDGE[k % 3].format(r1=risk1(c))} {ASK[(k + 1) % 3]}")

def choice(c, k):
    b = opt(c, c["best"])
    return CH[k % 3].format(n=b[0], a=b[1], d=b[2])

# ---------------- flows: each returns list of (user, tutor) ----------------
def f_thread(c, k):
    b = opt(c, c["best"])
    return [(OPENERS[k % 5] + c["need"], first_reply(c, k)),
            (c["a1"], f"Thanks, that helps. You said {q(c['a1'])}. I still need one more thing before we compare options: {low(c['q2'])}"),
            (c["a2"], cand_reply(c, k)),
            (choice(c, k), f"{PRAISE[k % 4]} Your advantage and your drawback both hold up. "
                           f"{c['why']}. You told me {q(c['a2'])}. If that changed, which part of your choice would you revisit first?")]

def f_early(c, k):
    b = opt(c, c["best"])
    return [(c["need"] + EARLY[k % 3].format(n=b[0]),
             f"Good that you have a candidate. Before I react, tell me two things: why the {b[0]}, and what could go wrong with it for your {c['product']}."),
            (f"Advantage: {b[1]}. Drawback: {b[2]}.",
             f"You named both an advantage and a drawback, which is honest. Now test the {b[0]} against your real conditions. {c['q1']} And {low(c['q2'])}"),
            (f"{c['a1']} {c['a2']}",
             f"With {q(c['a2'])}, your choice of the {b[0]} still fits. {c['why']}. "
             "Last question: what would you test on a sample before you order a large batch?")]

def f_wrong(c, k):
    b = opt(c, c["best"]); r = REVISIT[k % 3]
    return [(c["need"] + f" My plan: {c['mistake']}.", f"Let's test that idea first. {c['mq']}"),
            (f"{c['mr']} Maybe the {b[0]} instead?",
             f"You found the problem yourself: {q(head(c['mr']))}. That is the skill. Now justify the {b[0]}: give one advantage, one drawback, "
             "and how its relative cost compares with your first idea."),
            (f"Advantage: {b[1]}. Drawback: {b[2]}. Its cost is rated {b[3]} compared with the others.",
             f"That is a balanced answer. {c['why']}. Remember that cost per product sold includes losses, not just the unit price. "
             "If the conditions changed, for example a longer trip, more heat or a longer shelf life, what would you reconsider first?"),
            (r[0], r[1])]

def f_norules(c, k):
    alt = cheapest_other(c)
    return [(c["need"], first_reply(c, k + 1)),
            (f"{c['a1']} {c['a2']} {NOREG[k % 3]}",
             f"Understood, we will stay on materials. With {q(c['a2'])}, the main risks are {c['risk']}. "
             f"Candidates: {names(c, k)}. {ASK[k % 3]}"),
            (choice(c, k),
             f"{PRAISE[(k + 1) % 4]} {c['why']}. Now compare it with the {alt[0]}, which is rated {alt[3]} on relative cost here. "
             "Which loses you less money over a month of sales, once you count damage and spoilage and not just the unit price?")]

def f_legal(c, k):
    v = k % 3; b = opt(c, c["best"]); reg = re.split(r" (?:on|for) ", regshort(c))[0]
    extra = [" Is that legal? Please confirm it is approved.", " Please certify my pack.", ""][v]
    u3 = choice(c, k) + extra
    if v == 0:
        a3 = (f"I can't confirm that a pack is legal or approved, and I don't want you to rely on me for that. Only {reg} can tell you, "
              f"and your instructor can guide you. On design, your {b[0]} fits what you told me. To prepare, write down your product, "
              "ingredients, pack material and label wording. Which of those do you not have yet?")
    elif v == 1:
        a3 = (f"I can't certify a pack. Only {reg} can confirm what is acceptable, and your instructor can guide the process. "
              f"What I can do is help you get ready for that check, and your choice of the {b[0]} fits what you told me. "
              "Which do you not have yet: the material grade from your supplier, the label wording, or your storage conditions?")
    else:
        a3 = (f"{PRAISE[k % 4]} {c['why']}. Before we finish, which of your two answers "
              "would most change this choice if it were different?")
    if v == 2:
        u4 = "What about regulations?"
        a4 = (f"Good question. I can't tell you what the rules say, and they change, so please check with {reg}. "
              "Make a list for them: your product, ingredients, pack material and label wording. Which of those do you not have yet?")
    else:
        u4, a4 = LEGAL_FOLLOW[k % 3]; a4 = a4.format(reg=reg)
    return [(c["need"], first_reply(c, k)), (f"{c['a1']} {c['a2']}", cand_reply(c, k)), (u3, a3), (u4, a4)]

def f_changed(c, k):
    b = opt(c, c["best"]); ch = CHANGES[k % 3]
    return [(OPENERS[(k + 2) % 5] + c["need"], first_reply(c, k + 2)),
            (f"{c['a1']} {c['a2']}", cand_reply(c, k + 1)),
            (choice(c, k + 1),
             f"{PRAISE[(k + 2) % 4]} {c['why']}. Keep your two answers in view. "
             "If either of them changes, tell me and we will test the choice again. Which answer are you least sure about?"),
            (ch[0], f"Thanks for updating me. Earlier you said {q(c['a2'])}. {ch[1]} Which part of your {b[0]} choice is most affected: "
                    "the barrier, the strength of the pack, or the cost? Explain why.")]

def f_stuck(c, k):
    b = opt(c, c["best"])
    return [(c["need"] + " " + DEMAND[k % 3],
             f"I won't hand you the final answer, because you will have to defend it, but I'll get you most of the way. "
             f"Start here: what is the main thing that could damage or spoil {c['product']} between filling and the customer? Take a guess."),
            (STUCK[k % 3],
             f"That's fine. Here is a hint: for {c['product']} the main risks are {c['risk']}. Candidates: {names(c, k)}. "
             "Which one do you think protects best against those risks? A guess with a reason is enough."),
            (choice(c, k),
             f"{PRAISE[k % 4]} {c['why']}. You named {q(b[1])} as the advantage. Now one question: what would you check on a sample of this pack "
             "before using it for real sales?")]

CONCEPTS_OK = [x for x in CONCEPTS if x[0] not in ("migration", "labels", "foodgrade")]
def f_concept(c, k):
    cid, cq, expl, chk = CONCEPTS_OK[k % len(CONCEPTS_OK)]
    return [(c["need"], first_reply(c, k + 3)),
            (f"{c['a1']} {c['a2']} By the way, {low(cq)}",
             f"{expl} Back to your {c['product']}: you told me {q(c['a2'])}. {chk}")]

def f_cost(c, k):
    b = opt(c, c["best"]); alt = cheapest_other(c)
    return [(f"What is the cheapest packaging for my {c['product']}? My budget is tight.",
             "Cheapest per unit isn't always cheapest per sale. Spoilage, breakage, transport and supplier minimums all count. "
             f"First: {c['q1']}"),
            (f"{c['a1']} I guess the {alt[0]} is cheapest.",
             f"You guessed the {alt[0]} is cheapest. It does rate {alt[3]} on relative cost here, but check the trade-off: {alt[2]}. "
             f"Compare it with the {b[0]}: {b[1]}. Which loses you less money over a month of sales? "
             "I won't quote prices; get two or three supplier quotes in cedis."),
            ("So I should compare cost per product sold, including losses.",
             "Exactly. List these cost lines for each option: pack unit cost, minimum order, damage and spoilage, transport weight and filling effort. "
             f"Then add one line for the main trade-off of each: the {alt[0]}: {alt[2]}; the {b[0]}: {b[1]}. "
             "Fill in the table for your two options and tell me which wins and why.")]

def f_eol(c, k):
    b = opt(c, c["best"])
    return [(f"I chose the {b[0]} for my {c['product']}. What happens to it after use?",
             "Asking early is the right habit. First, where will your customers dispose of it: household bins, the street or collection points? "
             "And does anyone collect or reuse it in your area?"),
            ("Mostly households. Some collectors take plastic bottles and scrap, I'm not sure about the rest.",
             f"You said some collectors take plastic bottles and scrap. For this pack: {c['eol']} "
             "What could you, as the producer, do to improve this: design choices, labelling, reuse or take-back?"),
            ("Maybe offer refills or a return discount, and print a message not to litter.",
             "Good ideas that stay inside your control. Rank them by cost and by effect. Collection services differ by town, "
             f"so check what exists locally with {EPA_TXT}. Which one would you pilot first?")]

# ---------------- v3.1: behaviours from the instructor-round additions, scaled across the product cards ----------------
ADVISERS = ["My cousin", "My friend", "A trader at the market", "My uncle", "A neighbour who sells the same thing"]
TIER_RANK = {"low": 0, "medium": 1, "high": 2}

def f_hold(c, k):
    return [(f"{ADVISERS[k % 5]} says this is enough for my {c['product']}: {c['mistake']}. So I will skip anything else. Do you agree?",
             f"I can't agree yet, but let's test it. {c['mq']}"),
            (c["mr"],
             f"Good, you found the weak point yourself: {q(head(c['mr']))}. Does that advice still hold under your real conditions? "
             "Say what you would check before deciding.")]

def f_uncertain(c, k):
    b = opt(c, c["best"])
    if k % 2 == 0:
        a1 = ["I don't know what collectors near you accept. It changes by town and over time. Who could you ask, and what would you ask them?",
              "I can't tell what the collectors near you take, because it changes by town and over time. Who could you ask, and what would you ask?",
              "I don't have that local information, and it changes by town and over time. Who could you ask, and what would you ask them?"][k % 3]
        u2 = ["I could visit the collector at the market and ask what they buy.",
              "I could ask the waste office at my Assembly what is collected.",
              "I could ask a scrap dealer near me what they take."][k % 3]
        return [(f"Does the collector near me take the {b[0]}?", a1),
                (u2, "Good. Ask what they take, whether they pay for it, and whether they want it clean. "
                     f"Bring the answers back and we will compare options for your {c['product']} again.")]
    return [(f"Can I easily buy the {b[0]} near me?",
             "I don't know what suppliers near you stock, or what they ask for it. That changes by town and over time. "
             "Who could you ask, and what would you ask them?"),
            (["I could visit two suppliers and ask what they have.", "I could call a supplier in town and ask about minimum orders."][k % 2],
             "Good. Ask what they stock, whether there is a minimum order, and how long delivery takes. "
             f"Bring the answers back and we will compare options for your {c['product']} again.")]

def f_false(c, k):
    v = k % 3; b = opt(c, c["best"]); reg = re.split(r" (?:on|for) ", regshort(c))[0]
    if v == 0:
        u1 = f"My cousin said small {c['product']} sellers do not need to register, so I will skip it in my design."
        a1 = (f"I can't confirm that, and rules change, so please don't rely on what your cousin said. Ask {reg} and check with your instructor. "
              "Write down your product, ingredients, pack and label wording. Which of these do you not have yet?")
    elif v == 1:
        u1 = f"I heard the {b[0]} is already approved for {c['product']}, so I don't need to check anything."
        a1 = (f"I can't confirm that, and a general claim about a material may not cover your product, pack or label. Ask {reg} and check with your instructor. "
              "Which details do you not have yet: the material grade from your supplier, the label wording, or your storage conditions?")
    else:
        u1 = f"A shop owner told me I can skip the expiry date on my {c['product']} to save money. Is that fine?"
        a1 = (f"I can't confirm that, and rules change, so please check with {reg}. Think about it too: what would a customer do if the product "
              "spoiled earlier than expected? What shelf-life test could you run?")
    if v == 2:
        return [(u1, a1), ("I could keep samples in a shop-like place and check them regularly.",
                           "Good. Check them at regular intervals for spoilage, smell, texture and leaks, and write down what you see. What would tell you the pack failed?")]
    u2, a2 = LEGAL_FOLLOW[k % 3]
    return [(u1, a1), (u2, a2.format(reg=reg))]

def f_price(c, k):
    b = opt(c, c["best"]); alt = cheapest_other(c)
    u1 = [f"How much will the {b[0]} cost me per piece in cedis?", f"What is the price of the {b[0]} per piece?",
          f"Give me the cost in cedis of the {b[0]}."][k % 3]
    return [(u1, f"I can't give reliable prices, and they change by supplier and season. Ask two or three suppliers for quotes. "
                 f"For now, let's compare cost tiers. Would you rate the {b[0]} low, medium or high compared with the {alt[0]}, and what drives that?"),
            (f"I'd rate it {b[3]}. What drives it, I think, is this: {b[1]}.",
             f"Good, relative tiers are the right tool for now. Now check the other side: the {alt[0]} is rated {alt[3]} here, with the trade-off {q(alt[2])}. "
             "Which one loses you less money once you count damage and spoilage?")]

SCALE = [("Shops are far away now, so it travels by bus and some packs get damaged.", "Damage in transit is the new risk."),
         ("It sits longer on shop shelves than before.", None),
         ("More hands handle it now, and some packs come back opened.", "More handling raises the risk of contamination and tampering.")]
def f_scale(c, k):
    u2, imp = SCALE[k % 3]
    imp = imp or f"A longer time on the shelf raises the risk of {risk1(c)}."
    return [(f"My {c['product']} sells well now and I am selling to many more shops. Should I change my packaging?",
             "Good question. What has changed besides how much you sell: how far it travels, how long it sits on shelves, how many hands touch it? Tell me one change you have seen."),
            (u2, f"That is useful. {imp} What could you change: the pack itself, the outer carton or crate, or how it is loaded? Pick one and give one drawback.")]

DISC = ["I don't know. I keep getting these wrong. Maybe I am not good at this.", "I am confused. This is too hard for me.",
        "I always make mistakes with these questions."]
def f_disc(c, k):
    return [(f"I make {c['product']}. My plan: {c['mistake']}.", f"Let's test that idea. {c['mq']}"),
            (DISC[k % 3], "Being stuck is part of learning, and saying what you don't know is a good start. "
                          f"Take one small step: tell me just one thing that could harm your {c['product']} on its way to the customer. Then we will test your pack against it.")]

PERSIST = [("Please, just tell me. I will copy what you say.",
            "That is exactly why I won't: you would have to defend it yourself. Here is a small step. Pick one threat from this list: {risk}. Then pick one pack you would test against it. Two sentences is enough."),
           ("No. Just the answer, I don't have time.",
            "I hear you, and I'll keep it short. You still have to defend the choice, so start here. Pick one threat from this list: {risk}. Then name one pack you would test against it."),
           ("My lecturer will not know. Just give it to me.",
            "Even if nobody checks, a real client will ask you why. So let's build it quickly. Pick one threat from this list: {risk}, then one pack you would test against it. Two sentences is enough.")]
def f_persist(c, k):
    u2, a2 = PERSIST[k % 3]
    return [(f"Just give me the best packaging for my {c['product']}. I have a deadline.",
             f"I understand the pressure, but I won't hand you a final answer you can't defend. Let's make it quick: what is the main threat to {c['product']}? Give a best guess."),
            (u2, a2.format(risk=c["risk"]))]

def f_correct(c, k):
    b = opt(c, c["best"])
    o = max([x for x in c["opts"] if x[0] != c["best"]], key=lambda x: TIER_RANK[x[3]])
    return [(OPENERS[k % 5] + c["need"],
             f"Good place to start. I'll assume you have the equipment and suppliers to use any of these. Candidates: {names(c, k)}. Which fits you best, and why?"),
            (f"The {o[0]} looks good, but it is a problem for us: {o[2]}.",
             f"You caught something I should have asked first: your equipment, suppliers and budget. That rules out the {o[0]} for now. "
             f"Between the other two, which suits your {c['product']} better against {risk1(c)}, and what drawback would you plan for?"),
            (choice(c, k),
             f"{PRAISE[k % 4]} {c['why']}. You named a drawback; who in your business would handle it, and what would you do if it happened?")]

BURN = [("Refills. Customers bring a container and I refill it, so I use less plastic.",
         "Good option. Think about hygiene and who cleans the containers. Name one risk and one way you would manage it."),
        ("Take-back. I give a small discount when they return the empty pack.",
         "Good option. Think about who collects the packs, where you store them, and how you keep them clean. Name one risk and one way you would manage it."),
        ("Use less material, with a thinner pack.",
         "Careful: a thinner pack can tear or leak. What could go wrong with your {product}, and how would you test it?")]
def f_burn(c, k):
    u2, a2 = BURN[k % 3]
    return [(f"Customers here just burn plastic anyway, so I will choose the cheapest pack for my {c['product']}.",
             "I understand the cost pressure. But burning plastic gives off harmful smoke for people nearby, so it does matter. "
             "What could you do besides pick the cheapest pack: use less material, offer refills, or arrange take-back? Pick one and say what it would cost you."),
            (u2, a2.format(product=c["product"]))]

VAGUE_T = ["pack for {p} what do i use", "{p} packaging pls", "wat is best pack 4 {p}"]
def f_vague(c, k):
    return [(VAGUE_T[k % 3].format(p=c["product"]),
             f"Happy to help. I need a bit more first, because the right pack depends on your product. {c['q1']} And {low(c['q2'])}")]

NEW_FLOWS = [("hold_position", f_hold, 8), ("uncertainty", f_uncertain, 8), ("false_premise", f_false, 8), ("price_request", f_price, 8),
             ("scale_up", f_scale, 8), ("discouraged_student", f_disc, 8), ("over_reliance", f_persist, 8),
             ("tutor_correction", f_correct, 8), ("environmental_justice", f_burn, 8), ("vague_input", f_vague, 6)]

# Hand-written Pidgin-English dialogues: (card id, student, tutor, student, tutor). Words like 'three months' come from the student.
PIDGIN = [
 ("gari", "I dey make gari and I wan sell am for shop. Wetin be the best way to pack am?",
  "Happy to help. Let's take it step by step. Do you sell it in small packs for customers, in big bags for traders, or both? And how long does it stay in the shop or store before it is sold?",
  "I dey sell both. Sometimes e dey stay for shop three months, especially for rainy season.",
  "Thanks. So you sell both, and it can sit in the shop for about three months in the rainy season. Which risk matters most for gari then: moisture, insects, or the pack breaking? Give your best guess and one reason."),
 ("palmoil", "I wan sell my red palm oil for Accra. Which container I go use?",
  "Happy to help. Let's go step by step. How far will the oil travel, and how will you carry it: bus, truck or by hand? And will customers buy small bottles or big containers?",
  "E go travel by bus. Dem go buy small bottle and some go buy big gallon.",
  "Thanks. So the oil travels by bus, and you sell small bottles and big containers. Which risk matters most: leaking, light and air, or dirt getting in? Give your best guess and one reason."),
 ("shito", "I dey make shito for sell. Make you help me pick jar.",
  "Happy to help. Let's take it step by step. Is the shito filled hot or cold, and how long should it last before customers finish it?",
  "I dey fill am hot, and e must last like two months.",
  "Thanks. So you fill it hot, and it must last about two months. Which risk matters most: spoilage, leaking, or the jar breaking in transport? Give your best guess and one reason."),
 ("pepper", "I get dry pepper wey I wan sell. Wetin be the best pack?",
  "Happy to help. Let's take it step by step. Is the pepper whole or ground, and where is it kept before it is sold?",
  "E be ground pepper. I dey keep am for my room, e dey hot small.",
  "Thanks. So it is ground pepper, kept in a room that gets warm. Which risk matters most: moisture, losing its smell, or insects? Give your best guess and one reason."),
 ("groundnut", "I dey make groundnut paste. Which kind pack I fit use for market?",
  "Happy to help. Let's take it step by step. Is the paste sold in small portions or big containers, and how long should it stay good?",
  "Small small jar dem go buy, and e must stay good for two months.",
  "Thanks. So you sell small jars and it must stay good for about two months. Which risk matters most: air, oil leaking, or the lid not sealing? Give your best guess and one reason."),
 ("honey", "I get honey wey I wan sell for road. Which bottle be better?",
  "Happy to help. Let's take it step by step. Will customers buy small bottles or big containers, and how will the honey travel to the buyers?",
  "Small bottle, dem go carry am for bus go Kumasi.",
  "Thanks. So you sell small bottles and they travel by bus to Kumasi. Which risk matters most: leaking, breaking, or tampering? Give your best guess and one reason."),
 ("sobolo", "I dey sell sobolo. Wetin be the best bottle make I use?",
  "Happy to help. Let's take it step by step. Do you fill the drink hot or after it cools, and how long must it stay good?",
  "I dey fill am hot, and e must stay good for one week.",
  "Thanks. So you fill it hot, and it must stay good for about one week. Which risk matters most: the bottle softening, spoilage, or leaking? Give your best guess and one reason."),
 ("juice", "I dey make pineapple juice. How I go pack am for shop?",
  "Happy to help. Let's take it step by step. Do you fill the juice hot or cold, and how far are the shops from you?",
  "I dey fill am hot, shop dem near, same town.",
  "Thanks. So you fill it hot, and the shops are in the same town. Which risk matters most: spoilage, the bottle failing under heat, or breakage? Give your best guess and one reason."),
]
PIDGIN_SPLIT = {"honey": "val", "sobolo": "test"}

FLOWS = {"thread": f_thread, "early": f_early, "wrong_choice": f_wrong, "no_regulations": f_norules, "legal_request": f_legal,
         "changed_assumption": f_changed, "stuck_student": f_stuck, "concept_midway": f_concept, "cost": f_cost, "end_of_life": f_eol}
CORE = ["thread", "no_regulations", "wrong_choice"]
REGULATED = {"herbal", "infantcereal"}   # products whose risk list itself names regulation; no 'refuses regulation' flow
ROT = ["early", "legal_request", "changed_assumption", "stuck_student", "concept_midway", "cost", "end_of_life"]

def decline(topic, j):
    tid, users, ref, special = topic
    return special if special else f"{DECLINE_OPEN[(j + len(tid)) % 5]} {ref} {REDIRECT_V3[(j + len(tid)) % 5]}"

def build_new(heldout):
    rows = []
    for i, c in enumerate(CARDS):
        core = [("early" if (n == "no_regulations" and c["id"] in REGULATED) else n) for n in CORE]
        names_ = list(FLOWS) if c["id"] in heldout else core + [ROT[(i + 2 * j) % 7] for j in range(3)]
        names_ = list(dict.fromkeys(names_))
        for fi, name in enumerate(names_):
            k = i * 3 + fi
            pairs = FLOWS[name](c, k)
            rows.append(dict(id=f"{c['id']}-v3-{name}", group=c["id"], type=name, messages=msgs(*pairs)))
    train_cards = [c for c in CARDS if c["id"] not in heldout]
    for j, (name, fn, n) in enumerate(NEW_FLOWS):   # v3.1 behaviours: n train cards, every held-out card
        chosen = [train_cards[(j * 5 + t * 3) % len(train_cards)] for t in range(n)] + [c for c in CARDS if c["id"] in heldout]
        for c in chosen:
            k = CARDS.index(c) + j
            rows.append(dict(id=f"{c['id']}-v31-{name}", group=c["id"], type=name, messages=msgs(*fn(c, k))))
    for cid, u1, a1, u2, a2 in PIDGIN:
        rows.append(dict(id=f"pidgin-{cid}", group=f"pidgin-{cid}", type="code_switch", messages=msgs((u1, a1), (u2, a2))))
    for j, t in enumerate(SCOPE_TOPICS):          # v2 topics: first request only (keeps size down)
        rows.append(dict(id=f"scope3-{t[0]}-1", group=f"scope2-{t[0]}", type="scope", messages=msgs((t[1][0], decline(t, j)))))
    for j, t in enumerate(NEW_SCOPE_TOPICS):      # new topics: both requests
        for v, u in enumerate(t[1]):
            rows.append(dict(id=f"scope3-{t[0]}-{v+1}", group=f"scope3-{t[0]}", type="scope", messages=msgs((u, decline(t, j + v)))))
    return rows

# --------------------------- validation ---------------------------
BANNED = [r"\bguaranteed? (safe|compliant)\b", r"\b100% safe\b", r"\bfully compliant\b", r"\bI certify\b", r"\bGH[S¢₵]\s?\d", r"\$\d"]
REGWORDS = re.compile(r"regulat|Ghana FDA|Standards Authority|certif|legal|approved", re.I)
REG_FLOWS = {"false_premise", "legal_request", "verify_safety", "scope", "over_reliance", "concept", "concept_midway", "end_of_life", "mid_off_topic"}

def check(rows):
    problems, seen = [], set()
    for r in rows:
        m = r["messages"]; roles = [x["role"] for x in m]
        if roles[0] != "system" or roles[-1] != "assistant" or any(roles[i] == roles[i + 1] for i in range(len(roles) - 1)):
            problems.append((r["id"], "bad roles"))
        users = " ".join(x["content"] for x in m if x["role"] == "user")
        for x in m:
            if x["role"] != "assistant": continue
            t = x["content"]
            for p in BANNED:
                if re.search(p, t, re.I): problems.append((r["id"], p))
            for num in re.findall(r"\d+", t):
                if num not in users: problems.append((r["id"], f"number {num} not from student"))
            for ph in re.findall(r"\b((?:a few|several|one|two|three|four|five|six)\s+(?:day|week|month|year)s?)\b", t, re.I):
                if ph.lower() not in users.lower(): problems.append((r["id"], "shelf-life claim"))
            if len(t.split()) > 110: problems.append((r["id"], f"long reply {len(t.split())} words"))
            if r["type"] not in REG_FLOWS and r["group"] not in REGULATED and REGWORDS.search(t):
                problems.append((r["id"], "regulation words outside a regulation flow: " + REGWORDS.search(t).group(0)))
        key = json.dumps(m[1:], sort_keys=True)
        if key in seen: problems.append((r["id"], "duplicate"))
        seen.add(key)
    return problems

if __name__ == "__main__":
    v2 = {s: [json.loads(l) for l in open(f"data_v2/{s}.jsonl", encoding="utf-8")] for s in ("train", "val", "test")}
    split_of = {r["group"]: s for s, rs in v2.items() for r in rs}
    heldout = {g for g, s in split_of.items() if s != "train" and g in {c["id"] for c in CARDS}}
    # keep v2 rows that are not scripted per-card flows and not v2 scope (regenerated above with new wording)
    DROP = {"guided", "demand_answer", "wrong_choice", "cost", "end_of_life", "scope"}
    kept = [r for s in v2.values() for r in s
            if r["type"] not in DROP or (r["type"] == "scope" and not r["id"].startswith("scope2-") and re.match(r"scope\d\d$", r["id"]))]
    new = build_new(heldout)
    for r in new: r["meta"] = dict(source="synthetic_handwritten_v3", language="en", region="Ghana", needs_instructor_review=True)
    rows = kept + new
    problems = check(new)
    # hand-curated additions from the instructor round (kept in a separate file so rebuilds always include them)
    adds = []
    if os.path.exists("instructor_additions_v3a.jsonl"):
        adds = [json.loads(l) for l in open("instructor_additions_v3a.jsonl", encoding="utf-8")]
        # accepted exceptions: stated assumptions / questions about time, and a regulation reply in the false-premise case
        add_problems = [p for p in check(adds) if p[1] != "shelf-life claim" and not ("false-premise" in p[0] and "regulation words" in p[1])]
        print("additions:", len(adds), "unexpected problems:", add_problems or "none")
        rows += adds
    print("kept from v2:", len(kept), "new:", len(new), "total:", len(rows))
    print("problems in new rows:", len(problems))
    for p in problems[:60]: print("  ", p)

    # split: inherit v2 split by group, new groups by shuffle
    for r in adds:
        split_of.setdefault(r["group"], r["meta"].get("suggested_split", "train"))
    for cid, sp in PIDGIN_SPLIT.items():
        split_of.setdefault(f"pidgin-{cid}", sp)
    all_groups = sorted({r["group"] for r in rows})
    unseen = [g for g in all_groups if g not in split_of]
    rng.shuffle(unseen)
    for i, g in enumerate(unseen): split_of[g] = "test" if i == 0 else "val" if i == 1 else "train"
    os.makedirs("data_v3", exist_ok=True)
    out = {"train": [], "val": [], "test": []}
    for r in rows: out[split_of[r["group"]]].append(r)
    toks = lambda r: sum(len(m["content"].split()) for m in r["messages"]) * 1.34
    for s, rs in out.items():
        with open(f"data_v3/{s}.jsonl", "w", encoding="utf-8") as f:
            for r in rs: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        pairs = sum(sum(1 for m in r["messages"] if m["role"] == "assistant") for r in rs)
        print(f"{s}: dialogues {len(rs)}, training pairs {pairs}, est. max tokens {max(toks(r) for r in rs):.0f}")
    print(dict(collections.Counter(r["type"] for r in rows)))
    with open("data_v3/instructor_review_v3.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "type", "conversation", "factually_correct (Y/N)", "pedagogy_ok (Y/N)", "locally_realistic (Y/N)", "comments"])
        for r in new:
            conv = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in r["messages"] if m["role"] != "system")
            w.writerow([r["id"], r["type"], conv, "", "", "", ""])
    with open("data_v3/cards_for_review.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["card", "product", "main risks (correct? Y/N)", "options: advantage / drawback / relative cost (correct? Y/N)",
                    "best option and why (correct? Y/N)", "end-of-life statement (correct? Y/N)", "bodies to verify with (right? Y/N)", "comments"])
        for c in CARDS:
            o = "\n".join(f"- {x[0]}: + {x[1]}; - {x[2]}; cost {x[3]}" for x in c["opts"])
            w.writerow([c["id"], c["product"], c["risk"], o, f"{c['best']}: {c['why']}", c["eol"], "; ".join(c["reg"]), ""])
