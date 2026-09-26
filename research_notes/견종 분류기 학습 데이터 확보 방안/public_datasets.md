# Public dog/pet image datasets: licensing for a commercial on-device breed classifier

Context: free Google Play app (commercial), on-device classifier choosing among golden retriever, dachshund, welsh corgi, siberian husky, shiba inu (more may be added later). Research date: 2026-09-29. None of this is legal advice.

## Q1. Stanford Dogs and ImageNet: terms, image ownership, why they're unusable commercially, and whether evaluation-only use changes anything

### Takeaway
Stanford Dogs is a relabelled subset of ImageNet and has no license of its own. ImageNet's Terms of Access limit use to "non-commercial research and educational purposes" and put all copyright liability on the user, and the images belong to their original web photographers. Training a shipped commercial model on it is outside the terms. Using it for evaluation only is still a commercial use of the data under the ToA's plain wording, but it leaves nothing in the product, so the practical risk is much lower.

### Cited Findings
- Stanford Dogs: "built using images and annotation from ImageNet for the task of fine-grained image categorization". It has 120 categories, 20,580 images, class labels and bounding boxes. The homepage has no license or terms text of its own (checked the page source). — [Stanford Dogs homepage](http://vision.stanford.edu/aditya86/ImageNetDogs/main.html)
- The summary page says about 150 images per class. — [Stanford Dogs summary](http://vision.stanford.edu/aditya86/ImageNetDogs/menu_summary.html)
- The class list includes `golden_retriever`, `Siberian_husky`, `Pembroke`, `Cardigan`. It has **no dachshund and no shiba inu** class. — [HF mirror card, Donghyun99/Stanford-Dogs](https://huggingface.co/datasets/Donghyun99/Stanford-Dogs/blob/main/README.md). (Note: the d2l.ai write-up of the Kaggle version lists "Dachshunds" among the breeds, which conflicts with the class list. See Gaps.) — [d2l.ai](https://d2l.ai/chapter_computer-vision/kaggle-dog.html)
- ImageNet Terms of Access: "Researcher shall use the Database only for non-commercial research and educational purposes." — [image-net.org/download.php](https://image-net.org/download.php)
- ImageNet ToA: the researcher "shall defend and indemnify the ImageNet team, Princeton University, and Stanford University ... against any and all claims arising from Researcher's use of the Database, including ... use of any copies of copyrighted images". — [image-net.org/download.php](https://image-net.org/download.php)
- ImageNet ToA: "make no representations or warranties regarding the Database, including ... warranties of non-infringement". — [image-net.org/download.php](https://image-net.org/download.php)
- The Kaggle "Dog Breed Identification" competition data is "a strictly canine subset of ImageNet" (10,222 train and 10,357 test images, 120 breeds), which is effectively Stanford Dogs. — [d2l.ai description of the competition](https://d2l.ai/chapter_computer-vision/kaggle-dog.html); [Kaggle competition page](https://www.kaggle.com/competitions/dog-breed-identification) (the rules page renders client-side and could not be fetched)
- **License-laundering trap:** the "Dog CEO" Dog API image repo says "Original images provided by the Stanford Dogs Dataset", and the repo is GPL-3.0. A Kaggle re-upload of Dog CEO images is labelled "Public Domain / CC0". The CC0 label is not valid for images the uploader does not own. — [jigsawpieces/dog-api-images](https://github.com/jigsawpieces/dog-api-images); [Kaggle "Dog Breeds Image Dataset"](https://www.kaggle.com/datasets/darshanthakare/dog-breeds-image-dataset) (search-result snippet)

### Inferences
- Copyright in each image stays with the Flickr or other web photographer. ImageNet only distributes the images under a research-only access agreement, so no one in the chain can grant a commercial license. A Korean startup shipping weights trained on this data would be in breach of contract (the ToA) and also exposed on copyright, depending on jurisdiction (TDM or fair-use exceptions vary).
- Evaluation only: the ToA does not distinguish training from testing. Any use connected to a commercial product is outside "non-commercial research". The practical exposure is much smaller because no derived weights ship and nothing is redistributed. Stanford Dogs also lacks dachshund and shiba, so it can only benchmark three of the five templates. A cleaner option is to build the eval set from CC BY sources (Open Images) or from your own photos.
- ImageNet-pretrained backbones (e.g., the MobileNet/EfficientNet weights in torchvision/timm) raise a related but separate question: the weights' own licenses are usually Apache/BSD, but the data provenance is ImageNet. This is common industry practice and a gray area, not covered here.

### Gaps
- I could not render Kaggle's competition rules page (it is JavaScript-only), so the competition-specific data-use clause is not quoted.
- Per-breed image counts for golden_retriever, Siberian_husky, Pembroke and Cardigan in Stanford Dogs were not fetched. The only verified figure is "~150 images per class".
- I did not resolve the d2l.ai claim that the Kaggle set includes dachshunds against the Stanford class list. The class list is the primary source and has no dachshund.

## Q2. Oxford-IIIT Pet Dataset: license, image copyright, target-breed coverage

### Takeaway
The official page states CC BY-SA 4.0 "for commercial/research purposes", but it also says "copyright remains with the original owners of the images". So the CC license realistically covers the annotations and compilation, not the photos. Of the five target breeds it contains **only Shiba Inu** (about 200 images).

### Cited Findings
- "The dataset is available to download for commercial/research purposes under a Creative Commons Attribution-ShareAlike 4.0 International License." — [Oxford-IIIT Pet page](https://www.robots.ox.ac.uk/~vgg/data/pets/)
- "The copyright remains with the original owners of the images." — [Oxford-IIIT Pet page](https://www.robots.ox.ac.uk/~vgg/data/pets/)
- It has 37 classes (25 dog and 12 cat breeds), "roughly 200 images for each class". Dog breeds include Shiba Inu, Samoyed, Pomeranian, Pug, Beagle and others. It has **no golden retriever, dachshund, corgi or siberian husky**. — [Oxford-IIIT Pet page](https://www.robots.ox.ac.uk/~vgg/data/pets/)
- 7,349 images in total, split about 50 train, 50 val and 100 test per breed. — [Parkhi et al. 2012 paper](https://www.robots.ox.ac.uk/~vgg/publications/2012/parkhi12a/parkhi12a.pdf) (via search snippet; the PDF download timed out)

### Inferences
- The "commercial" wording invites use, but the page disclaims image ownership. A CC BY-SA grant from Oxford therefore cannot license the photos themselves. Treat this as medium risk: it is better than ImageNet (no non-commercial clause and an explicit "commercial" mention), but the images' rights are unresolved.
- It adds only about 200 Shiba images, which is low value for the target set. It is also useful as "other breed / not a template" negatives.

### Gaps
- The exact Shiba Inu image count from Table 1 of the paper is unverified (the PDF fetch failed). "~200" comes from the official page.
- The page does not say where the images were collected (the paper reportedly used web sources such as Flickr and Google Images, but this is not verified here).

## Q3. Other candidates: Tsinghua Dogs, DogFaceNet, Kaggle sets, Open Images V7, LAION-5B/COYO, HF/Roboflow, AI Hub

### Takeaway
**Open Images V7 is the only large source with a per-image commercial-friendly license trail.** Its annotations are CC BY 4.0, each image is listed as CC BY 2.0 with author and URL metadata, and it has explicit labels for all five target breeds. Google still disclaims any warranty on image licenses. Tsinghua Dogs has no stated data license (the MIT on its GitHub repo covers code). DogFaceNet is CC BY 4.0 on Zenodo but web-scraped with no breed labels. LAION and COYO are URL lists whose images keep their owners' copyright, and both recommend research use only. AI Hub (Korea) needs a separate agreement for commercial use.

### Cited Findings

**Open Images V7**
- "The annotations are licensed by Google LLC under CC BY 4.0 license. The images are listed as having a CC BY 2.0 license." — [Open Images V7 facts & figures](https://storage.googleapis.com/openimages/web/factsfigures_v7.html)
- The key caveat: "we make no representations or warranties regarding the license status of each image and you should verify the license for each image yourself." — [Open Images V7 facts & figures](https://storage.googleapis.com/openimages/web/factsfigures_v7.html)
- Per-image metadata has these columns: `ImageID, Subset, OriginalURL, OriginalLandingURL, License, AuthorProfileURL, Author, Title, ...`. The sample row has License `https://creativecommons.org/licenses/by/2.0/` and a Flickr author. This makes attribution and license re-checks feasible. — [Open Images download page](https://storage.googleapis.com/openimages/web/download_v7.html); [train-images-boxable-with-rotation.csv](https://storage.googleapis.com/openimages/2018_04/train/train-images-boxable-with-rotation.csv)
- The class list (`oidv7-class-descriptions.csv`) includes `/m/01t032 Golden retriever`, `/m/02cj3 Dachshund`, `/m/01ksq5 Welsh Corgi`, `/m/02kh2h Pembroke welsh corgi`, `/m/02kgrx Cardigan welsh corgi`, `/m/071jj Siberian husky`, `/m/0119sz04 Husky`, `/m/077hh Shiba inu`, and `/m/0bt9lr Dog`. — [oidv7-class-descriptions.csv](https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions.csv)
- Image-level labels are **human-verified positives** (Confidence=1). I counted these by streaming the official CSVs:

  | Class | train | validation | test |
  |---|---|---|---|
  | Golden retriever | 3,599 | 36 | 98 |
  | Dachshund | 349 | 21 | 58 |
  | Siberian husky | 460 | 31 | 111 |
  | Shiba inu | 110 | 14 | 58 |
  | Welsh Corgi (generic) | 160 | 16 | 60 |
  | Pembroke welsh corgi | 150 | 16 | 54 |
  | Cardigan welsh corgi | 149 | 5 | 31 |
  | Dog (all) | 92,766 | 1,593 | 4,897 |

  — computed from [oidv7-train-annotations-human-imagelabels.csv](https://storage.googleapis.com/openimages/v7/oidv7-train-annotations-human-imagelabels.csv), [val](https://storage.googleapis.com/openimages/v7/oidv7-val-annotations-human-imagelabels.csv), [test](https://storage.googleapis.com/openimages/v7/oidv7-test-annotations-human-imagelabels.csv). The corgi classes overlap: one image may carry both "Welsh Corgi" and "Pembroke". A full re-run over all 58,783,034 train rows (last ImageID `fffffdaec951185d`, so the whole file was read) confirmed the train counts. Positives may still be partly mislabeled, so spot-check them.
- Open Images also has machine-generated labels (`oidv7-*-machine-imagelabels.csv`), which would add more candidates but are noisier. — [Open Images download page](https://storage.googleapis.com/openimages/web/download_v7.html)

**Tsinghua Dogs**
- 130 breeds, 70,428 images, 200 to 7,449 per breed, "over 65% of images are collected from people's real life", with breed frequency proportional to China. There are head and body bounding boxes. The project page has **no license or terms text**. It only has the line "Please cite our Tsinghua Dogs in your publications if it helps your research". — [ThuDogs project page](https://cg.cs.tsinghua.edu.cn/ThuDogs/)
- The GitHub repo shows an MIT License, and the images are hosted on cloud.tsinghua.edu.cn. — [dejungle/Tsinghua-Dogs](https://github.com/dejungle/Tsinghua-Dogs)

**DogFaceNet**
- The code is MIT. Per the README, the images were "retrieved from the web and aligned". The newer set has about 8,600 pictures. — [GuillaumeMougeot/DogFaceNet](https://github.com/GuillaumeMougeot/DogFaceNet)
- The Zenodo record (June 28, 2024) is licensed "Creative Commons Attribution 4.0 International". Images are organized by individual dog identity, **with no breed labels**. — [Zenodo 12578449](https://zenodo.org/records/12578449)

**LAION-5B / COYO-700M**
- LAION: "We distribute the metadata dataset (the parquet files) under the Creative Common CC-BY 4.0 license", and "The images are under their copyright." "Our recommendation is therefore to use the dataset for research purposes". It advises against "creating ready-to-go industrial products". — [LAION-5B blog](https://laion.ai/blog/laion-5b/)
- COYO: "licensed under CC-BY-4.0" (the dataset of URLs and text). "The collected data (images and text) is subject to the license to which each content belongs." It is "recommended to be used for research purposes", and Kakao Brain "does not recommend using this dataset as it is without special processing ... to create commercial products". The repo was archived on 2025-10-08. — [kakaobrain/coyo-dataset](https://github.com/kakaobrain/coyo-dataset)

**Hugging Face / Kaggle / Roboflow Universe re-uploads**
- Hugging Face lets you filter by license (e.g., cc0-1.0, cc-by-4.0), but the license tag is uploader-declared. — [HF cc-by-4.0 filter](https://huggingface.co/datasets?license=license%3Acc-by-4.0)
- A Roboflow community thread documents a CC BY-NC-SA 4.0 dataset being re-uploaded as CC BY 4.0 without attribution. Roboflow Universe licenses are uploader-declared. — [Roboflow forum](https://discuss.roboflow.com/t/my-dataset-was-used-with-an-inappropriate-license/11399); [Roboflow licensing](https://roboflow.com/licensing)
- Example: there is a "Stanford dogs" project on Roboflow Universe, so ImageNet data circulates there under whatever license the uploader picked. — [Roboflow Universe stanford-dogs](https://universe.roboflow.com/igor-romanica-gmail-com/stanford-dogs-0pff9)

**AI Hub (Korea): "반려동물 구분을 위한 동물 영상" (dataSetSn=59)**
- Dogs and cats, 514 hours of behavior video. "내국인만 데이터 신청이 가능합니다" (only Korean nationals may apply). The page lists no breeds. — [AI Hub dataset 59](https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=59)
- Policy: "AI 허브에서 제공하는 AI 데이터셋의 판매 등 상업적 이용을 희망하는 경우 수행기관과 별도 협의가 필요합니다" (commercial use requires a separate agreement with the executing agency). Attribution is required ("한국지능정보사회진흥원의 사업결과임을 밝혀야"), redistribution is prohibited, and export abroad needs an agreement. — [AI Hub 이용정책](https://www.aihub.or.kr/intrcn/guid/usagepolicy.do?currMenu=151&topMenu=105)

### Inferences
- Open Images is the best fit. Golden retriever has plenty of images. Dachshund and husky have hundreds each. Shiba (~180 across splits) and corgi (~450 unique at most across the corgi labels) are thin but usable for fine-tuning a pretrained backbone, and can be topped up with the app team's own or consented photos. Filter each image by its `License` column. Keep the `Author` and `OriginalLandingURL` columns for an attribution file. Re-check a sample of links, since Flickr owners can change licenses. Flickr's later license change does not revoke an already-granted CC BY 2.0, but it cannot be proven after the fact without a record, so keep the CSV rows.
- Tsinghua Dogs: silence plus "if it helps your research" plus an MIT repo is not a data license. The MIT covers the repo's code and annotations at most, not photos collected from users and the web. Treat it as all-rights-reserved: research or evaluation only, and contact the authors for commercial permission.
- DogFaceNet: the CC BY 4.0 is declared by the dataset authors on web-scraped photos, so the same "can't license what you don't own" problem applies. It also has no breed labels, so it has little value here.
- LAION/COYO: you can legally use the URL lists, but training on the fetched images depends entirely on each image's own license and on TDM exceptions. They are not a clean commercial source.
- AI Hub: the dataset is domestic-only and commercial use needs negotiation. It is video with no documented breed labels, so it is low value for a breed classifier.

### Gaps
- I did not measure what share of the Open Images target-breed positives actually carry `License` = CC BY 2.0. That needs joining with the image metadata CSV, which was not done.
- I did not find per-breed counts for Tsinghua Dogs in the target breeds. The project page and README don't list them; the annotation files would need to be downloaded.
- I did not survey specific HF or Roboflow dog-breed datasets one by one. Any candidate needs a provenance check; many are Stanford Dogs or Oxford re-uploads.
- I found no dataset-specific commercial terms for AI Hub #59 beyond the general policy.

## Q4. Share-alike and model weights; attribution obligations

### Takeaway
Creative Commons' own guidance (2025) says CC terms apply only where copyright permission is needed. If a model trained on ShareAlike material is "shared publicly", ShareAlike would require the same license. Whether trained weights are an "adaptation" is legally unsettled. Attribution for training "could be a simple link to the source of the dataset".

### Cited Findings
- "CC licenses apply only when copyright permission is required. If exceptions or limitations apply, then the CC license terms don't apply." — [Creative Commons, Using CC-licensed Works for AI Training](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)
- "If AI models or outputs are based on ShareAlike content and they will be shared publicly, following the ShareAlike condition would require AI developers to use the same CC license as the original works." — [Creative Commons, same page](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)
- "For AI model training, attribution could be a simple link to the source of the dataset used to train the model." — [Creative Commons, same page](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)

### Inferences
- An on-device model inside an APK is distributed publicly. If you trained on Oxford-IIIT Pet (BY-SA) and the weights count as an adaptation, CC's guidance suggests the weights would have to be released under BY-SA. The app code would not be covered, but extracting and reusing the model would then be permitted. For a small classifier this may be acceptable, but it is cleaner to avoid BY-SA sources or keep them in evaluation only.
- CC BY (Open Images images and annotations, DogFaceNet): put a credits or open-source-licenses screen in the app with a link to the dataset, and ideally a hosted attribution list (author and URL per image).

### Gaps
- I found no court decision on whether trained weights are an "adaptation" under CC BY-SA. Only CC's guidance is cited. Korean copyright law's TDM or fair-use position (Art. 35-5) was not researched here.

## Q5. Practical risk ranking (for training weights shipped in a commercial app)

### Takeaway
From lowest to highest risk: (1) your own or consented photos → (2) Open Images V7 filtered to CC BY 2.0 with an attribution file → (3) Oxford-IIIT Pet (BY-SA, images not owned; Shiba only) → (4) DogFaceNet (CC BY on scraped images; no breeds) → (5) Tsinghua Dogs (no data license) → (6) LAION/COYO fetched images (owner copyright, research recommended) → (7) Stanford Dogs, ImageNet, Kaggle Dog Breed Identification and Dog CEO re-uploads (explicitly non-commercial ToA; CC0 relabels are laundering). AI Hub sits apart: its terms are clear, but commercial use needs a negotiated agreement.

### Cited Findings
- ImageNet is non-commercial only, with indemnity. — [image-net.org](https://image-net.org/download.php)
- Open Images: CC BY 4.0 annotations and CC BY 2.0 images, with the warranty disclaimer. — [Open Images V7](https://storage.googleapis.com/openimages/web/factsfigures_v7.html)
- Oxford: CC BY-SA 4.0, but "copyright remains with the original owners". — [Oxford-IIIT Pet](https://www.robots.ox.ac.uk/~vgg/data/pets/)
- LAION/COYO: images keep their owners' copyright, and research use is recommended. — [LAION](https://laion.ai/blog/laion-5b/); [COYO](https://github.com/kakaobrain/coyo-dataset)

### Inferences
- Recommended plan: train the five-way head on Open Images CC BY 2.0 positives (checking `License` per row), plus consented user or team photos for Shiba and corgi. Use an ImageNet-pretrained lightweight backbone, which is common practice (flag it as a residual gray area). Keep Stanford Dogs and Oxford for internal benchmarking only, if at all, and never ship them.
