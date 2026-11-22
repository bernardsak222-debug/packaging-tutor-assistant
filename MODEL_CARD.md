# Model Card: Packaging Technology Teaching Assistant

A small language model that coaches packaging students by asking questions. It is a LoRA fine-tune of Gemma 3 1B instruct, built by Team Boadu as a capstone project.

## Model details
- Base model: `gemma3_instruct_1b` (Gemma 3 1B instruct), loaded through Keras Hub with the PyTorch backend.
- Method: LoRA, rank 8, 1,304,576 trainable parameters, float32, sequence length 768.
- Training: AdamW (learning rate 1e-4, weight decay 0.01), batch size 1, 3 epochs, on a free Colab T4 GPU. Training took 77.3 minutes.
- Data: 875 training pairs and 184 validation pairs. See `DATA_CARD.md`.
- Weights: `packaging_tutor_v3.lora.h5` (about 5 MB). Link: [https://drive.google.com/drive/folders/1TCqqplRUnLx6wliSU7jNkiwJqAqaor4R?usp=sharing]
- To use it, load the base model, then call `model.backbone.load_lora_weights(...)` on the file.

## Intended use
A teaching demo for packaging students in Ghana. The tutor asks about the product, the climate and the route, then helps the student compare materials, costs and end-of-life options.

## Not for
Regulatory, legal, medical or food-safety decisions. It cannot certify that a pack meets Ghana FDA or Ghana Standards Authority rules. It should not write assignments or answer exams for students.

## Training results
| epoch | loss | val_loss |
|---|---|---|
| 1 | 0.172 | 0.129 |
| 2 | 0.097 | 0.092 |
| 3 | 0.064 | 0.080 |

Validation loss fell every epoch, so there was no sign of overfitting in 3 epochs. The validation set holds three products the model never trained on (liquid soap, smoked fish, soy milk).

## Test results
We ran the model on 43 sampled turns from the test set. Shea butter and black soap are held out of training entirely. The replies are in `evaluation/eval_v3_test_samples.csv`. I read all 43 and counted by hand, so these are rough figures, not an automatic score.

What worked:
- Opening questions and the cost and end-of-life flows closely match the references.
- It declines off-topic requests (politics, code) and redirects to packaging.
- It refuses to quote a price and asks where the student would buy.

What did not work:
- About 10 of 43 replies add a long "verify with Ghana FDA / I can't certify compliance" paragraph in the middle of a conversation when the student did not ask. This was a main complaint from testers.
- 3 replies invent numbers or content, for example a made-up price calculation in cedis and a made-up label text.
- 2 replies suggest materials that were not in the scenario.
- Some of the newer behaviours are weak. In one over-reliance case the model gave a final answer when it should have kept asking. In one case it said "I can't help with that" instead of asking the student who to check with.
- Rare stray text, such as a full-width bracket and a nonsense sentence.

## Guard layer
The demo wraps the model in keyword rules that decline off-topic requests and add a reminder to confirm regulatory points with the official bodies. The rules are crude and have blocked valid questions (for example, one containing the word "weather"). The evaluation above was run on the model alone, without the guard.

## Limitations
- It is a 1B model trained on synthetic data covering 32 products, so it makes mistakes and can state wrong facts about materials, prices and local suppliers.
- It sometimes falls back on older script-like replies and loses the thread after several turns.
- Pidgin-English support rests on 8 short examples and has not been checked by a native speaker.
- The training data has not been fully verified by a packaging expert.
- Every answer needs checking by an instructor and the official sources.

## Planned improvements
- Remove the regulation paragraph unless the student asks about rules, and flag any number the student did not give.
- Add more examples for the weak behaviours, then retrain.
- Have an instructor fill in the review sheets and a native speaker check the Pidgin examples.

## Feedback collected
Team members tested a Gradio demo in November 2026 and left ratings and comments. Their main points were that the tutor loses the thread after turn 2 or 3, jumps to regulations too early, and invents facts such as shelf-life times. Version 3 of the dataset was built to address these.
