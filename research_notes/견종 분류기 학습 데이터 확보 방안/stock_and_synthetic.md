# Stock Photography vs. Synthetic Images as Training Data for a Commercial Dog-Breed Classifier

Context: free commercial mobile app, on-device breed classifier. Breeds: golden retriever, dachshund, welsh corgi, siberian husky, shiba inu (+ more later). Need ~300–2,000 images per breed. Research date: 2026-09-29.

## (A1) Do paid stock licenses (Shutterstock, Getty/iStock, Adobe Stock, Alamy, Depositphotos) permit ML training? Do data-licensing products exist?

### Takeaway
No. Every major paid stock agency's standard/enhanced license explicitly bans using licensed images for ML/AI training. Training rights are sold only through separate, sales-negotiated "data licensing" products (Shutterstock, Getty, Alamy "Novel Use", Depositphotos datasets) with no published self-serve price; publicly known deals are enterprise-scale ($25–50M) and the only industry price benchmark found is ~$1–2 per image.

### Cited Findings
- **Shutterstock (standard license):** prohibits using any Visual Content "as training data for any artificial intelligence, machine learning, or generative AI system, tool, process, or dataset" (same restriction for Licensed Music). Direct fetch of the license page returned HTTP 403; wording taken from search-indexed text of the page — [Shutterstock License](https://www.shutterstock.com/license)
- **Shutterstock data licensing:** separate product; buyers of Shutterstock datasets (content + metadata) "may only use them to train machine learning and computer vision models"; contributors are paid via a Contributor Fund — [Shutterstock Contributor help: Data Licensing and the Contributor Fund](https://submit.shutterstock.com/help/en/articles/10594694-shutterstock-data-licensing-and-the-contributor-fund); product page [shutterstock.com/data-licensing](https://www.shutterstock.com/data-licensing) (403 on fetch; no public price list found)
- **Shutterstock pricing scale:** Shutterstock's CFO said initial data deals with Apple, Meta, Google, Amazon were $25–50M each; industry rates cited as roughly $1–2 per image, $2–4 per short video — [VentureBeat](https://venturebeat.com/ai/apples-25-50-million-shutterstock-deal-highlights-fierce-competition-for-ai-training-data) (secondary report of a Reuters story)
- **Getty Images / iStock (Content License Agreement §3(k)):** "Unless explicitly authorized in a Getty Images invoice, sales order confirmation or license agreement, you may not use content (including any caption information, keywords or other metadata…) for any machine learning and/or artificial intelligence purposes, or for any technologies designed or intended for the identification of natural persons." Narrow exception: AI use on creative content only for internal archiving/search/indexing/sorting and permitted editing — [Getty Images EULA](https://www.gettyimages.com/eula) (wording from search-indexed text)
- **Getty data licensing:** Getty offers AI/ML data licensing from 572M+ assets (200M+ creative); a free 3,750-image, 15-category sample dataset is on Hugging Face under terms restricting redistribution and building products that directly compete with Getty — [Getty AI Data Licensing request page](https://engage.gettyimages.com/ai-sample-data-set-request); [Hugging Face: Getty-Images-Sample-Dataset](https://huggingface.co/datasets/GettyImages/Getty-Images-Sample-Dataset); [VentureBeat](https://venturebeat.com/data-infrastructure/getty-images-drops-cleanest-visual-dataset-for-training-foundation-models). No public pricing found.
- **Adobe Stock (Product Specific Terms, dated 2026-01-16):** prohibits using assets "to directly or indirectly create, train, test, or otherwise improve any machine learning algorithms or artificial intelligence systems, including any architectures, models, or weights," or with technologies for identifying natural persons; the ban applies equally to Unmetered/Unlimited plans, Pro Assets and the Adobe Stock API — [Adobe Stock Product Specific Terms PDF (2026-01-16)](https://www.adobe.com/cc-shared/assets/pdf/legal/servicetou/stock-product-specific-terms-en-us-20260116.pdf); [Adobe Stock PSLT 2024v1](https://www.adobe.com/content/dam/cc/en/legal/terms/enterprise/pdfs/PSLT-Stock-WW-2024v1.pdf)
- **Alamy:** license bars using content in AI tools "for the purposes of image generation or machine learning training"; ML use is available only via Alamy's "Novel Use" licensing (contributors opt in and get paid) — [Alamy US Terms](https://www.alamy.com/terms/us/); [Alamy Contributor Terms](https://www.alamy.com/terms/contributor/) (from search summaries, not direct fetch)
- **Depositphotos:** markets a dedicated AI-training data service (330M+ files, off-the-shelf and custom datasets with annotations) and says stock can be used for AI training "only when properly licensed for AI training" — [Depositphotos blog: Rights-Cleared AI Data Licensing 2026](https://blog.depositphotos.com/rights-cleared-ai-data-licensing.html)
- Regular (non-data) Shutterstock subscriptions run ~$0.22–0.57/image, but those licenses do not include training rights — [Shutterstock pricing summary (checkthat.ai, secondary)](https://checkthat.ai/brands/shutterstock/pricing)

### Inferences
- Buying 1,500–10,000 dog photos on a normal Shutterstock/iStock/Adobe subscription and training on them would breach the license, even for a small classifier. The license, not copyright law, is the binding constraint.
- Data-licensing products exist but are built for foundation-model buyers. For ~10k images, expect a custom quote; at the ~$1–2/image benchmark that is roughly $2k–20k for 1.5k–10k images, if a vendor will even take a deal that small. Unverified: no vendor publishes a minimum.
- Getty/Adobe also ban "identification of natural persons" tech. That does not apply to a dog classifier, but people often appear in dog photos (owners).
- The Getty HF sample (15 broad categories) is unlikely to contain breed-level dog labels in useful numbers. Not checked.

### Gaps
- No published price, minimum order, or self-serve SKU for Shutterstock, Getty, Alamy Novel Use, or Depositphotos data licenses. All are "contact sales."
- Could not fetch the full Shutterstock license, Getty EULA, or Alamy terms directly (HTTP 403 / not fetched). Clauses are quoted from search-indexed page text; the section numbers and dates should be checked in a browser.
- Did not research iStock's separate terms page (iStock is Getty-owned and generally follows Getty's Content License Agreement; not verified).

## (A2) Do free-photo sites (Pexels, Pixabay, Unsplash / Unsplash+) allow building datasets or ML training?

### Takeaway
The short "license" pages of Pexels and Pixabay say nothing about ML, but their Terms of Service (both updated Nov 2024; both sites are owned by Canva) ban scraping and automated collection "including without limitation for machine learning purposes," and ban bulk/systematic copying without permission. Unsplash's Terms explicitly ban using images in "any machine learning and/or artificial intelligence datasets" and send such requests to unsplash.com/data. None is a safe free source of training data.

### Cited Findings
- **Pexels License page:** allows free use and modification. Prohibitions cover selling unaltered copies, redistributing on other stock/wallpaper platforms, use in trademarks, and misrepresenting people. No ML clause on the license page itself — [Pexels License](https://www.pexels.com/license/)
- **Pexels Terms of Service (last updated 2024-11-15):** "Data mining, extraction, scraping and the use of programs or robots for automatic data collection and/or extraction of digital data on the Service and/or the content available therein is strictly prohibited for all unauthorised purposes, including without limitation for machine learning purposes." Also: "Bulk, large-scale or systematic copying of Content is strictly prohibited unless explicit permission has been granted by us." — [Pexels Terms of Service](https://www.pexels.com/terms-of-service/)
- **Pixabay License summary:** no ML/dataset clause. It bans standalone sale/distribution, commercial use of content with recognisable trademarks, and immoral/misleading use — [Pixabay License Summary](https://pixabay.com/service/license-summary/)
- **Pixabay Terms (last updated 2024-11-18):** has the same scraping clause "…including without limitation for machine learning purposes" and the same bulk-copying ban as Pexels — [Pixabay Terms of Service](https://pixabay.com/service/terms/)
- **Unsplash License:** "This license does not include the right to compile images from Unsplash to replicate a similar or competing service." — [Unsplash License](https://unsplash.com/license)
- **Unsplash Terms §8 (prohibited):** "Use the Images in connection with any machine learning and/or artificial intelligence datasets (e.g., training any machine learning and/or artificial intelligence models), or for technologies designed or intended for the identification of natural persons." Permission requests go to [unsplash.com/data](https://unsplash.com/data). Bots/scrapers are also banned except through the official API under the API Terms — [Unsplash Terms](https://unsplash.com/terms)
- The Unsplash+ license is a separate document (/plus/license) and was not fetched — [Unsplash License](https://unsplash.com/license)

### Inferences
- **Pexels/Pixabay:** a narrow literal reading might allow hand-downloading a few hundred images one by one, since only "scraping/automated" and "bulk, large-scale or systematic" copying are named. But 300–2,000 images × 5+ breeds is plainly "systematic," and the ML wording shows the platform's intent. Treat as not permitted without written permission from Pexels/Pixabay (Canva).
- **Unsplash:** explicitly prohibited. Unsplash+ very likely inherits the Unsplash Terms §8 ban (unverified).
- All three ToS let the platform train on uploaders' content (with opt-out). That is a separate matter and does not grant rights to downloaders.

### Gaps
- Unsplash+ license text not checked. Unsplash's "data" program terms and pricing not checked.
- Whether Pexels/Pixabay would grant written permission, and on what terms, is unknown.

## (B1) May outputs of image generators be used commercially, and specifically to train another (classifier) model?

### Takeaway
For a dog-breed classifier, the cleanest options are local open-weight models with permissive licenses: FLUX.1 [schnell] / FLUX.2 [klein] 4B (Apache 2.0), SDXL (CreativeML OpenRAIL++-M), and SD 3.5 under Stability's Community License (free below $1M revenue; only bans building foundational generative models). Hosted APIs (OpenAI, Gemini/Imagen, Midjourney paid tiers) let users own or use outputs commercially. Their "don't build competing models" clauses target models that compete with the provider's own service, which a breed classifier arguably does not. FLUX.1 [dev] / FLUX.2 [klein] 9B under the non-commercial license are the ones to avoid: training a model for commercial use is expressly "not a Non-Commercial Purpose."

### Cited Findings
- **FLUX.1 [dev] Non-Commercial License v1.1.1:** "We claim no ownership rights in and to the Outputs." Outputs may be used commercially, except "You may not use the Output to train, fine-tune or distill a model that is competitive with the FLUX.1 [dev] Model or the FLUX.1 Kontext [dev] Model." Crucially, running the model itself is restricted to Non-Commercial Purpose, and "use (a) for revenue-generating activity, (b) in direct interactions with or that has impact on end users, or (c) to train, fine tune or distill other models for commercial use, in each case is not a Non-Commercial Purpose." — [FLUX.1-dev LICENSE.md](https://huggingface.co/black-forest-labs/FLUX.1-dev/blob/main/LICENSE.md)
- **FLUX.2 [klein] (released 2026-01-15):** 4B and 9B sizes. The 4B is Apache 2.0; the 9B is under FLUX Non-Commercial License. The 4B runs in ~13GB VRAM and generates in under ~0.5s on modern GPUs — [BFL blog: FLUX.2 [klein]](https://bfl.ai/blog/flux2-klein-towards-interactive-visual-intelligence); [VentureBeat](https://venturebeat.com/technology/black-forest-labs-launches-open-source-flux-2-klein-to-generate-ai-images-in); FLUX.2 [dev] 32B needs a paid license for commercial deployment — [bestfreewebresources Flux license guide 2026 (secondary)](https://www.bestfreewebresources.com/flux-lora-licence-guide-2026). FLUX.1 [schnell] is Apache 2.0 (per task brief; BFL now positions FLUX.1 as previous generation — [Flux (Wikipedia)](https://en.wikipedia.org/wiki/Flux_(text-to-image_model)))
- **SDXL, CreativeML Open RAIL++-M:** "Except as set forth herein, Licensor claims no rights in the Output you generate using the Model." There is no ban on commercial use or on training other models with outputs. Only the Attachment A use-based restrictions apply (e.g., harming minors, harmful disinformation, discrimination) — [SDXL base 1.0 LICENSE.md](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md)
- **Stability AI Community License (covers SD 3.5 etc., updated 2024-07-05):** "You own any outputs generated from the Models or Derivative Works to the extent permitted by applicable law." The license terminates if you or affiliates exceed USD $1,000,000 annual revenue (an Enterprise license is then needed). Restriction: "You will not use the Stability AI Materials or Derivative Works… to create or improve any foundational generative AI model" — [Stability AI Community License](https://stability.ai/community-license-agreement)
- **OpenAI Terms of Use:** users may not "Use Output to develop models that compete with OpenAI." The full page returned 403; wording confirmed via search index. The terms assign ownership of Output to the user (standard clause, not re-fetched) — [OpenAI Terms of Use](https://openai.com/policies/row-terms-of-use/)
- **Gemini API Additional Terms (effective 2026-03-23, page updated 2026-04-28):** "You may not use the Services to develop models that compete with the Services (e.g., Gemini API or Google AI Studio)." On generated content: "Google won't claim ownership over that content." Unpaid tier inputs/outputs may be used to improve Google products and seen by human reviewers; paid tier data is not used for training — [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)
- **Midjourney ToS:** users own Assets they create "to the fullest extent possible under applicable law." Companies (or their employees) with >$1M/yr revenue must be on Pro or Mega to own assets. Per secondary analyses, Free/Basic tiers don't carry commercial rights while Standard/Pro/Mega do. Users grant Midjourney a perpetual, irrevocable license to their outputs — [Midjourney ToS](https://docs.midjourney.com/hc/en-us/articles/32083055291277-Terms-of-Service) (403 on direct fetch); [terms.law Midjourney 2026 guide (secondary)](https://terms.law/ai-output-rights/midjourney/). Midjourney offers no official public API for bulk generation (general knowledge; not re-verified here).

### Inferences
- **"Compete" clauses (OpenAI, Gemini, FLUX dev, Getty sample):** these target models that substitute for the provider's product (general image/LLM services). A dog-breed image classifier is a discriminative model and doesn't compete with an image generator or a general multimodal API, so the most natural reading permits it. Gemini's wording ("develop models that compete with the Services") is broader, since Gemini can itself classify dog breeds from photos. That is a small residual risk worth a lawyer's glance if Gemini/Imagen is chosen.
- **FLUX.1 [dev]:** the output clause alone looks permissive, but the separate rule that the model may only be run for Non-Commercial Purposes, which excludes "(c) to train… other models for commercial use," makes generating training data for a commercial app off-limits without a paid BFL commercial license. Same for FLUX.2 [klein] 9B / FLUX.2 [dev].
- **Stability Community License:** fine for a free app unless the company/affiliates pass $1M revenue. A classifier is not a "foundational generative AI model."
- **Midjourney:** commercially usable on paid tiers. Batch generation of thousands of images is impractical without an API, and ToS automation limits apply (not verified in detail).
- **Copyright caveat:** purely AI-generated images may not be copyrightable, so the app owner may hold no exclusive rights in the synthetic dataset. That doesn't affect using it for training.

### Gaps
- Could not directly fetch the OpenAI or Midjourney ToS (403). Exact current wording on output ownership and any Midjourney clause on using outputs to train other models is unverified.
- Did not verify whether Vertex AI (Imagen via Google Cloud) Service Specific Terms carry the same "competing models" clause as the Gemini API terms.
- No 2026 update found for the Stability Community License beyond the 2024-07-05 version. Did not check whether SD 3.5's successor models changed terms.

## (B2) Do classifiers trained on synthetic images generalize to real photos? (fine-grained evidence, domain gap, mixing ratios)

### Takeaway
Evidence is mixed but consistent in direction: synthetic-only training works surprisingly well at ImageNet scale yet lags real data, especially for fine-grained classes. Synthetic data works best as augmentation mixed with real images (peaks commonly reported at ~20–60% synthetic) with diverse prompts and domain-gap handling. A 2024 study found that simply retrieving real images beat synthetic images from the same generator.

### Cited Findings
- **Sariyildiz et al., "Fake it till you make it" (CVPR 2023):** ImageNet clones generated by Stable Diffusion from class names alone train classifiers with "surprisingly good" performance. The gap to real-trained models shrinks under domain shift and adversarial tests, and the models perform on par across 15 transfer datasets — [arXiv 2212.08420](https://arxiv.org/abs/2212.08420); [CVF paper](https://openaccess.thecvf.com/content/CVPR2023/papers/Sariyildiz_Fake_It_Till_You_Make_It_Learning_Transferable_Representations_From_CVPR_2023_paper.pdf)
- **"Diversify, Don't Fine-Tune" (2023):** diversifying prompts with LLM/CLIP-disambiguated class names plus contextual/style diversification, and handling the domain shift with auxiliary batch-norm, lets synthetic data up to 6× ImageNet size keep improving accuracy. This contradicts earlier findings that results degrade once synthetic outnumbers real, and gives strong out-of-domain generalization — [arXiv 2312.02253](https://arxiv.org/abs/2312.02253)
- **"The Unmet Promise of Synthetic Training Images" (2024):** real images retrieved from the generator's own training set (LAION-2B) "universally" match or beat task-targeted synthetic images from Stable Diffusion. Causes: generator artifacts and inaccurate task-relevant visual details — [arXiv 2406.05184](https://arxiv.org/abs/2406.05184)
- **Mixing ratio:** in diffusion-augmentation studies on fine-grained few-shot benchmarks (including Stanford Dogs, 120 breeds / 20,580 images), accuracy typically peaks with synthetic at 20–60% of training data; DA-Fusion, Real-Guidance, Diff-Mix are standard baselines — [SGD-Mix arXiv 2505.11813](https://arxiv.org/pdf/2505.11813); [Diff-Mix, CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/papers/Wang_Enhance_Image_Classification_via_Inter-Class_Image_Mixup_with_Diffusion_Model_CVPR_2024_paper.pdf); [Systematic analysis of diffusion augmentation, arXiv 2603.08364](https://arxiv.org/pdf/2603.08364) (ratio figure from search summary; exact per-paper numbers not extracted)
- Further fine-grained synthetic-data work (contextual generation, hierarchical guidance) exists for 2025 — [arXiv 2510.24078](https://arxiv.org/html/2510.24078v1); [HiGFA arXiv 2511.12547](https://arxiv.org/pdf/2511.12547)

### Inferences
- For 5 very popular breeds, a mix of a real-photo core (even a few hundred per breed from rights-clear sources or user-consented photos) plus synthetic augmentation is the evidence-backed approach. Synthetic-only is riskier for fine-grained distinctions (e.g., shiba inu vs. akita, husky vs. malamute, pembroke vs. cardigan corgi).
- The test/validation set must be real photos. Otherwise synthetic-to-real gap problems stay hidden.
- Prompt diversity (pose, age/puppy, coat color variants, indoor/outdoor, phone-camera look, occlusion, lighting) matters more than raw volume.

### Gaps
- No paper found that tests exactly the "5 common breeds, ~1k images/breed, mobile-quality photo" setting. Exact Stanford Dogs accuracy deltas for synthetic vs. real were not extracted.

## (B3) Breed fidelity risk: do generators render less common breeds correctly? Is human filtering needed?

### Takeaway
Generators handle very popular breeds (golden retriever, husky, corgi, shiba, dachshund) reasonably, but fine-grained accuracy drops for rarer categories. One study reports Stable Diffusion images of CUB bird species were recognizable only ~40% of the time. Automatic plus human filtering is needed, especially as rarer breeds are added.

### Cited Findings
- Stable Diffusion generates fine-grained classes (CUB-200 bird species) with only ~39.7% accuracy, and CLIP gives near-identical similarity to rare fine-grained names and their coarse labels, making CLIP a weak judge for rare concepts — [Discriminative Class Tokens, arXiv 2303.17155](https://arxiv.org/pdf/2303.17155); [Generating images of rare concepts, arXiv 2304.14530](https://arxiv.org/pdf/2304.14530) (figures via search summary; the exact paper each number comes from was not confirmed by direct fetch)
- A confusion analysis for generated "kuvasz" images spread predictions across similar large light-colored breeds (kuvasz 30.5%, malamute 20.7%, Great Pyrenees 10.9%, Eskimo dog 9.0%) — reported in one of the above papers per search summary (exact source unconfirmed)
- Text encoders mix up entities ("a cat is a cat, not a dog") in multi-object prompts — [arXiv 2410.00321](https://arxiv.org/html/2410.00321v1)
- The "Unmet Promise" paper names "inaccurate representation of visual details relevant to specific tasks" as a key failure of synthetic training data — [arXiv 2406.05184](https://arxiv.org/abs/2406.05184)

### Inferences
- Suggested pipeline: generate about 1.5–2× the target count → auto-filter with a pretrained real-photo breed classifier (e.g., a Stanford-Dogs/ImageNet model), keeping only confident, correct predictions → quick human spot-check → dedupe. A real-trained filter guards against training on the generator's systematic breed errors.
- Watch-outs by breed (general domain knowledge, not from a source): corgi pembroke vs. cardigan (tail, ears), dachshund coat types (smooth/long/wire), shiba vs. akita vs. Jindo (relevant for a Korean user base), husky vs. malamute. Class definitions should match the app's label set.
- Risk grows sharply for less common breeds added later. There, real data or generator fine-tuning (LoRA/DreamBooth on a handful of rights-clear real photos) becomes necessary.

### Gaps
- No quantitative benchmark found for per-breed generation accuracy of current (2026) generators (FLUX.2, Imagen 4, gpt-image-1.5/2).

## (B4) Cost and throughput: local GPU vs. hosted API

### Takeaway
Synthetic generation is cheap at this scale. 5 breeds × 2,000 images = 10k keepers; with ~50% filter loss, ~20k generations cost roughly $25–60 on FLUX schnell-class APIs, ~$100–700 on OpenAI mini/low or Imagen 4 Fast/Standard, and effectively only electricity/GPU-hours locally (FLUX.2 klein 4B: sub-second per image on a ~13GB-VRAM GPU). By comparison, licensed-stock training data needs a negotiated data license (benchmark ~$1–2/image, i.e., $10k–20k for 10k images, if available at all).

### Cited Findings
- **OpenAI GPT Image:** 1024×1024 costs $0.011 (low) to $0.167 (high) on gpt-image-1; mini variants $0.005–0.036. The original gpt-image-1 is reportedly being retired 2026-10-23, with gpt-image-1.5 / GPT Image 2 as successors — [pricepertoken GPT image pricing (secondary)](https://pricepertoken.com/gpt-image-pricing); [costgoat OpenAI image pricing Sep 2026 (secondary)](https://costgoat.com/pricing/openai-images)
- **Google Imagen 4:** Fast $0.02, Standard $0.04, Ultra $0.06 per image — [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing); [magichour Imagen 4 pricing (secondary)](https://magichour.ai/blog/imagen-4-pricing-and-api)
- **FLUX.1 [schnell] via API:** Together AI ~$0.0027 per megapixel; cheapest listed provider ~$0.0012/image — [Together AI](https://www.together.ai/models/flux-1-schnell); [Pixazo (secondary)](https://www.pixazo.ai/blog/flux-schnell-api-cheapest-pricing); BFL's own pricing — [bfl.ai/pricing](https://bfl.ai/pricing)
- **Local FLUX.2 [klein] 4B:** Apache 2.0, ~13GB VRAM (RTX 3090/4070+), <0.5s per image on modern hardware — [VentureBeat](https://venturebeat.com/technology/black-forest-labs-launches-open-source-flux-2-klein-to-generate-ai-images-in); [BFL blog](https://bfl.ai/blog/flux2-klein-towards-interactive-visual-intelligence)
- **Stock data license benchmark:** ~$1–2/image — [VentureBeat](https://venturebeat.com/ai/apples-25-50-million-shutterstock-deal-highlights-fierce-competition-for-ai-training-data)

### Inferences
- **Worked estimate for 20k generations (10k keepers):**
  - FLUX schnell API at $0.0012–0.003 ≈ $25–60
  - gpt-image mini/low at $0.005–0.011 ≈ $100–220
  - Imagen 4 Fast/Standard at $0.02–0.04 ≈ $400–800
  - Local klein 4B at ~0.5–2s/image ≈ 3–11 GPU-hours
  Human spot-check time will likely cost more than compute.
- **Apple Silicon:** on a Mac (the user's platform is macOS), local generation runs much slower than on a CUDA GPU. Using a cloud GPU or a cheap Apache-2.0 model API is probably the pragmatic choice (not benchmarked).
- **Licensing ranking for a free commercial app:** local Apache-2.0 models (FLUX.1 schnell, FLUX.2 klein 4B) and SDXL are the lowest-risk, followed by the Stability Community License (<$1M revenue), then the OpenAI/Imagen APIs (the "compete" clause is probably not triggered). Avoid FLUX [dev]/klein 9B without a commercial license, and avoid Midjourney Free/Basic.

### Gaps
- Pricing figures for OpenAI and Imagen partly come from third-party aggregators. Official pages should be checked at purchase time since models and prices changed through 2026 (gpt-image-1 retirement, GPT Image 2).
- No measured throughput for FLUX.2 klein on Apple Silicon (MPS/MLX).
