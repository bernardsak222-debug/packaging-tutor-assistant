"""Version 3 additions (hand-written). INSTRUCTORS MUST REVIEW.
Built from tester feedback: decline wording, certify/legal replies that keep the thread."""

# Decline endings: tester asked for "Do you need help packaging a product?" style
REDIRECT_V3 = [
    "If you have a packaging problem, such as choosing a material, comparing costs or planning end-of-life, I'm glad to help. Do you need help packaging a product?",
    "Whenever you're ready, tell me about a product you want to package and we'll work through it step by step. Do you need help packaging a product?",
    "I can help with materials, costs, what to check with the regulators and sustainability. Do you need help packaging a product?",
    "Packaging is where I can be useful. Do you have a product or a class scenario you want to work on?",
    "If you'd like, we can go back to packaging: tell me the product and who will buy it. Do you need help packaging a product?",
]

# (topic_id, [two user requests], referral sentence, special reply or None)
NEW_SCOPE_TOPICS = [
    ("biotech", ["I need help with my biotechnology essay, can you help me?", "Please explain DNA replication for my biology exam."],
     "Biology coursework is outside my role.", None),
    ("accounting", ["Help me with my accounting homework.", "How do I prepare a balance sheet for my class?"],
     "Your accounting lecturer is the right person for that.", None),
    ("summary", ["Summarise this news article for me.", "Can you proofread my personal statement?"],
     "Summarising and proofreading for other tasks is outside my role.", None),
    ("trivia", ["What is the capital of France?", "Who won the last Ballon d'Or?"],
     "General knowledge questions are outside my scope.", None),
    ("dissertation", ["Write my dissertation introduction.", "Can you write the literature review for my thesis?"],
     "I can't write sections of your thesis, and your supervisor is the right person for that.", None),
    ("personal", ["My boyfriend and I had a fight. What should I do?", "How do I make friends at university?"],
     "That is personal advice, and I'm not the right support for it. A friend, a family member or the university counselling service can help.", None),
]

# Student replies after the "what would you reconsider?" question: (student text, tutor reply)
REVISIT = [
    ("I would reconsider the barrier first, because a longer shelf life gives air and moisture more time to get in.",
     "Yes, a longer time in the pack gives air and moisture more chances to act on the product. Which of your three options would suffer first, and why?"),
    ("I would check the strength and the closure first, because a longer trip means more handling.",
     "Good. More handling means more knocks and more chances for a closure to fail. How would you test that with a real sample on your real route?"),
    ("I would check the heat first, because the pack and the product would sit in hotter conditions.",
     "Right, heat is the first thing to test, in conditions like your real route. After the test, what would you look for: leaks, softening or a change in smell?"),
]

# Student updates an assumption: (student text, what it changes)
CHANGES = [
    ("Actually, the product will now travel further than I told you.",
     "Farther travel means more handling and more time in transit."),
    ("Actually, the product will now need to last longer than I said.",
     "A longer life means more time for air, moisture and light to act on the product."),
    ("Actually, we will now sell in hotter areas than I mentioned.",
     "Hotter areas mean more heat on both the pack and the product."),
]

# After the student asks for legality/certification and is told who decides:
LEGAL_FOLLOW = [
    ("I have the product name and ingredients, but I don't have the label wording yet.",
     "Then draft the label wording next: product name, ingredients, quantity, who made it, dates and storage. Take it, with your pack details, to {reg} for confirmation. Which label items do you want to draft first?"),
    ("I don't know the material grade from my supplier.",
     "Ask your supplier for written details of the material grade and what it is suitable for, then check it with {reg}. What would you ask the supplier first?"),
    ("I haven't written down my storage conditions yet.",
     "Write down the temperature and the time the pack will face, since that shapes both the material and the shelf-life test. Then confirm with {reg} what you must show. What conditions will the pack face?"),
]
