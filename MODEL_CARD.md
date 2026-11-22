# Model Card: Packaging Technology Teaching Assistant (LoRA on Gemma 3 1B)

## Model
- Base: `gemma3_instruct_1b` (Gemma 3 1B instruct), via Keras Hub, PyTorch backend.
- Fine-tuning: LoRA rank 8 (1,304,576 trainable parameters), float32, sequence length 768.
- Training: AdamW lr 1e-4, weight decay 0.01, batch size 1, up to 3 epochs, early stopping on validation loss, free Colab T4 GPU.
- Data: see `DATA_CARD.md` (v3.1: 875 training pairs, 184 validation pairs).
- Weights: [LINK TO LORA FILE, Drive or Hugging Face]

## Intended use
A conversational tutor that coaches packaging students through material choice, cost trade-offs, end-of-life and sustainability by asking questions, rather than handing over final answers. For teaching and demonstration only.

## Out of scope
Regulatory, legal, medical or food-safety decisions; exam answers or writing assignments for students; any use as a certification of compliance.

## Guard layer (outside the model)
Keyword rules decline off-topic requests, add a reminder to confirm regulatory points with Ghana FDA / Ghana Standards Authority, and block unsafe advice. These rules are crude and can misfire.

## Evaluation
[TO FILL after running the evaluation notebook: test loss/accuracy, comparison with v2 and the 270M model, held-out products, and teammate feedback.]

## Known limitations
- Can lose the thread after a few turns and sometimes follows scripted patterns.
- May state facts about materials or local availability incorrectly; always verify with an instructor and official sources.
- Trained on synthetic data covering 32 products; weaker on unseen products.
- Pidgin-English support is small and unreviewed by a native speaker.
- Small model: expect errors.

## Ethical notes
The tutor is built to encourage the student's own reasoning and to say when it is unsure. Teammate feedback was collected through a Gradio demo.
