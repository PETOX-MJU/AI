# Openly licensed web dog photos for a commercial breed classifier + Korean copyright rules for ML training

Scope: golden retriever, dachshund, welsh corgi, siberian husky, shiba inu; a few thousand photos; model shipped on-device in a free commercial Korean mobile app. Research date 2026-09-29. Live API checks were run on that date (numbers below come from those checks).

## Q1. Which CC licenses allow commercial ML training? What does Creative Commons say about AI training?

### Takeaway
CC0, PDM and CC BY are safe for commercial training and shipping the model. CC BY-SA is allowed, but CC says a shared model may have to carry the same license. NC rules out commercial use at every stage, and CC says ND content should not be used as training data. The app ships the model file inside the APK, so the model counts as "shared" for these conditions.

### Cited Findings
- CC's guidance page "Using CC-Licensed Works for AI Training" says: "CC licenses apply only when copyright permission is required. If exceptions or limitations apply, then the CC license terms don't apply." So whether you even need the license depends on local law (fair use/TDM). — [Creative Commons](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)
- Attribution (BY): CC says that for AI training, attribution could be "a simple link to the source of the dataset used to train the model." — [Creative Commons](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)
- ShareAlike (SA): if models based on SA content are shared publicly, developers must "use the same CC license as the original works." — [Creative Commons](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)
- NonCommercial (NC): "all stages, from copying the data during training to sharing the trained model, must not be for commercial gain." — [Creative Commons](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)
- NoDerivatives (ND): CC recommends that "ND-licensed content not be used as training data." — [Creative Commons](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)
- Timing: BY, SA and ND conditions apply only when the work is shared publicly. NC applies to every use that needs copyright permission, including private training. — [Creative Commons](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)

### Inferences
- Safe whitelist for a commercial app: CC0 1.0, Public Domain Mark, and CC BY (2.0/2.1 jp/2.5/3.0/4.0).
- Drop all NC and ND licenses. Even if a Korean fair-use defense might cover them, CC's own reading of NC ("all stages") makes them a bad fit for a commercial product. Excluding them costs little.
- BY-SA is a policy decision. An on-device model is distributed to every user, so if a court or CC treated the model as an adaptation, SA would require releasing the model under CC BY-SA. The conservative option is to exclude BY-SA, or to keep SA images in a separate pool and measure whether they are really needed. On Wikimedia Commons, BY-SA is a large share (about 47% of a 200-file Shiba Inu sample, see Q3), so excluding it roughly halves the Commons yield.
- "Commercial" here covers a free app too. NC is about commercial purpose, not about charging money, so a company-run free app with ads, in-app purchases or a business motive should be treated as commercial. (This is an inference. CC's NC definition was not fetched in this session.)

### Gaps
- CC's longer AI FAQ and legal analysis, including whether a trained model is "Adapted Material" under the 4.0 licenses, was not fetched in full. CC's own framing is that this depends on the case and on jurisdiction.

## Q2. How do you satisfy attribution for thousands of training images when only the model is shipped?

### Takeaway
CC itself accepts a link to the dataset source as sufficient AI-training attribution. Common practice is a machine-readable attribution manifest (one row per image: title, author, source URL, license and version, modifications) published at a stable URL, plus a short in-app "Data credits / Open-source licenses" screen that links to it.

### Cited Findings
- CC: attribution for AI training could be "a simple link to the source of the dataset used to train the model." — [Creative Commons](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)
- CC's attribution conditions apply only on public sharing. — [Creative Commons](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/)
- Openverse returns a ready-made attribution string for each image, e.g. `"Shiba inu" by Yuya Tamai is licensed under CC BY 2.0. To view a copy of this license, visit https://creativecommons.org/licenses/by/2.0/.`, which can go straight into the manifest. — [Openverse API live response](https://api.openverse.org/v1/images/?q=shiba%20inu&license=by,cc0,pdm,by-sa&page_size=1)
- The Wikimedia Commons API returns license metadata per file through `prop=imageinfo&iiprop=extmetadata` (fields such as LicenseShortName, and Artist/Credit on the same endpoint). This was confirmed in a live query. — [Commons API](https://commons.wikimedia.org/w/api.php?action=query&generator=categorymembers&gcmtitle=Category:Shiba_Inu&gcmtype=file&gcmlimit=200&prop=imageinfo&iiprop=extmetadata|mime&iiextmetadatafilter=LicenseShortName&format=json)

### Inferences
- Recommended practice:
  1. At collection time, store per image: source, source page URL, author, license short name, license URL and version, retrieval date, and a SHA-1/pHash.
  2. Publish that `attribution.csv` as a static file (a GitHub repo or the project site) with a short dataset card.
  3. In the app's settings, under "오픈소스 라이선스 / 학습 데이터 출처", add one sentence and a link.
- Shipping all attributions inside the app is probably not required, because CC accepts a link. Adding the link costs almost nothing and covers the case where the model is treated as a shared adaptation.
- Keep the manifest even for CC0/PDM images. It gives provenance proof if a takedown or complaint arrives, and it supports the "lawful access" arguments used in the Korean fair-use analysis.

### Gaps
- I found no court decision, in Korea or elsewhere, on whether a shipped image-classifier model triggers CC attribution. The practice above is based on CC's own guidance, not on case law.

## Q3. Wikimedia Commons: categories, counts, license mix, bulk tooling, quality

### Takeaway
Commons has a few hundred directly categorized files per breed, and more in subcategories: puppies, heads, poses, coat varieties. Every license in a sampled category was free (no NC/ND), but about half were BY-SA. The MediaWiki API is enough for bulk collection. Expect art, skeletons, famous-dog subcategories and a small share of non-photo files, which need filtering.

### Cited Findings (live `categoryinfo` query, 2026-09-29; "files" counts direct members only, not subcategories)
- Category:Golden Retriever: 534 files, 16 subcats (including Golden Retriever puppies, heads, Lying/Running/Sitting golden retrievers, Golden Retriever in water; also Golden Retriever skeletons and Golden Retriever hybrids, which should be excluded). — [Commons API](https://commons.wikimedia.org/w/api.php?action=query&prop=categoryinfo&titles=Category:Golden_Retriever&format=json)
- Category:Dachshund: 384 files, 16 subcats (coat/size varieties such as Smooth/Long-Haired/Wire-Haired Standard/Miniature/Rabbit Dachshund, puppies; plus "Dachshunds in art", skeletons, hybrids and a museum category to exclude). — [Commons API](https://commons.wikimedia.org/w/api.php?action=query&prop=categoryinfo&titles=Category:Dachshund&format=json)
- Category:Siberian Husky: 315 files, 14 subcats (puppies, heads, country subcats such as Huskies in Germany/Russia/the Philippines/the United States; also "Siberian Huskies in art", hybrids, "Siberian-Askal", and historical "Dogs of the Terra Nova Expedition" and Balto). — [Commons API](https://commons.wikimedia.org/w/api.php?action=query&prop=categoryinfo&titles=Category:Siberian_Husky&format=json)
- Category:Shiba Inu: 267 files, 7 subcats (puppies, Mino Shiba Inu, Jomon Shiba Inu, and meme or individual dogs such as Kabosu and Cheems the Dog, plus "Shiba Inu in art"). — [Commons API](https://commons.wikimedia.org/w/api.php?action=query&prop=categoryinfo&titles=Category:Shiba_Inu&format=json)
- Category:Pembroke Welsh Corgi: 91 files, 3 subcats (puppies, in art, Sutter Brown). Parent Category:Welsh Corgi: 66 files, with subcats Cardigan Welsh Corgi, Pembroke Welsh Corgi, Royal corgis, Welsh Corgi in China/Vietnam, hybrids and "Scarecrows of Welsh Corgi". The plural names (e.g. "Category:Golden Retrievers") do not exist or are empty. — [Commons API](https://commons.wikimedia.org/w/api.php?action=query&prop=categoryinfo&titles=Category:Pembroke_Welsh_Corgi&format=json)
- License mix, 200-file sample of Category:Shiba Inu: CC BY 2.0 61, CC BY-SA 4.0 45, CC0 27, CC BY-SA 2.0 26, CC BY-SA 3.0 21, Public domain 10, CC BY 4.0 3, CC BY 3.0 3, CC BY 2.1 jp 3, CC BY-SA 2.5 1. That is about 107 of 200 (54%) in the CC0/PD/BY group and 93 of 200 (47%) BY-SA. MIME types: 190 JPEG, 9 PNG, 1 Ogg (video/audio). — [Commons API](https://commons.wikimedia.org/w/api.php?action=query&generator=categorymembers&gcmtitle=Category:Shiba_Inu&gcmtype=file&gcmlimit=200&prop=imageinfo&iiprop=extmetadata|mime&iiextmetadatafilter=LicenseShortName&format=json)

### Inferences
- Rough yield: direct files across the 5 breeds come to about 1,600 (534+384+315+267+91+66). Adding photo-type subcategories (puppies, poses, coat varieties, country subcats) could reach about 2,500–3,500. Keeping only CC0/PD/BY roughly halves that. Commons alone probably cannot supply "a few thousand" clean BY-or-better photos per breed. It is a good seed, and Flickr through Openverse or the Flickr API should be the main volume source.
- Corgi is the thinnest class (Pembroke 91 direct files). Decide whether to merge Pembroke and Cardigan into one "welsh corgi" class or keep them separate.
- Tooling (live-verified pattern): `action=query&generator=categorymembers&gcmtype=file&gcmlimit=500&prop=imageinfo&iiprop=url|mime|size|extmetadata&iiurlwidth=1024`. Recurse into a hand-picked whitelist of subcategories, not the whole tree. Download the thumbnail size (`iiurlwidth`), not originals, and send a descriptive User-Agent with contact info, per Wikimedia API etiquette. Full Commons dumps are overkill for a few thousand files.
- Quality filters: drop `mime != image/jpeg|png`; drop anything under "in art", "skeletons", "hybrids", "Scarecrows", or historical/individual famous-dog subcats; drop non-photos (drawings, stamps, statues such as "Pomnik Szczęśliwego Psa"). Run a pretrained dog detector (e.g. COCO "dog" class) to reject images with no dog or several dogs, and a person detector to flag people.
- The absence of NC/ND in the sample is consistent with Commons policy of accepting only free licenses. (I did not fetch the policy page this session; see [Commons:Licensing](https://commons.wikimedia.org/wiki/Commons:Licensing).)

### Gaps
- Recursive (deep) file counts per breed were not computed. Only direct membership and subcat names were checked.
- Mislabel rate on Commons was not measured. It needs a manual audit of a sample.

## Q4. Flickr, Openverse, iNaturalist, Unsplash, Pexels: license filters and ML-specific terms

### Takeaway
Flickr and Openverse are the usable volume sources: filter to CC0, PDM and CC BY by license id or code. iNaturalist has almost no breed-level data, because breeds are not taxa. Unsplash's Terms of Service now explicitly prohibit ML/AI dataset use, and Pexels' ToS prohibit scraping "for machine learning purposes" and bulk copying without permission. Despite their permissive-looking licenses, both should be excluded unless you get written permission.

### Cited Findings
- Flickr license ids (`flickr.photos.licenses.getInfo`): 0 All Rights Reserved; 1 CC BY-NC-SA 2.0; 2 CC BY-NC 2.0; 3 CC BY-NC-ND 2.0; 4 CC BY 2.0; 5 CC BY-SA 2.0; 6 CC BY-ND 2.0; 7 No known copyright restrictions (Flickr Commons); 8 United States Government Work; 9 CC0; 10 Public Domain Mark; 11 CC BY 4.0; 12 CC BY-SA 4.0; 13 CC BY-ND 4.0; 14 CC BY-NC 4.0; 15 CC BY-NC-SA 4.0; 16 CC BY-NC-ND 4.0. — [Flickr API](https://www.flickr.com/services/api/flickr.photos.licenses.getInfo.html)
- `flickr.photos.search` takes a comma-separated `license` parameter: "Multiple licenses may be comma-separated." — [Flickr API](https://www.flickr.com/services/api/flickr.photos.search.html)
- Openverse API: `GET /v1/images/?q=shiba inu&license=by,cc0,pdm,by-sa` returns per-image `source`, `license`, `license_version` and a full `attribution` string. The top result for shiba inu came from Flickr under CC BY 2.0. An anonymous request reported `result_count` = 240. — [Openverse API](https://api.openverse.org/v1/images/?q=shiba%20inu&license=by,cc0,pdm,by-sa&page_size=1)
- iNaturalist API: taxon 47144 is *Canis familiaris* (species rank). Observations of that taxon with `photo_license=cc0,cc-by,cc-by-sa` total 5,811. Adding a breed text query returned only Shiba Inu 3, Golden Retriever 19, Dachshund 1, Pembroke Welsh Corgi 0, Siberian Husky 3. — [iNaturalist API](https://api.inaturalist.org/v1/observations?taxon_id=47144&photo_license=cc0,cc-by,cc-by-sa&per_page=0)
- Unsplash Terms, Prohibited Conduct: users may not "Use the Images in connection with any machine learning and/or artificial intelligence datasets (e.g., training any machine learning and/or artificial intelligence models), or for technologies designed or intended for the identification of natural persons." The terms point to https://unsplash.com/data for other arrangements. They also ban bots/scrapers except the API under the API Terms. — [Unsplash Terms](https://unsplash.com/terms)
- The Unsplash License page itself does not mention ML. Its compilation restriction is "Compiling images from Unsplash to replicate a similar or competing service." — [Unsplash License](https://unsplash.com/license)
- The Pexels License page does not mention ML. It forbids reselling unaltered copies and redistributing on other stock/wallpaper platforms. — [Pexels License](https://www.pexels.com/license/)
- Pexels Terms of Service: "Data mining, extraction, scraping and the use of programs or robots for automatic data collection ... is strictly prohibited for all unauthorised purposes, including without limitation for machine learning purposes." and "Bulk, large-scale or systematic copying of Content is strictly prohibited unless explicit permission has been granted by us." — [Pexels Terms](https://www.pexels.com/terms-of-service/)

### Inferences
- Flickr query for the whitelist: `license=4,7,8,9,10,11` (BY 2.0, No known restrictions, US Gov, CC0, PDM, BY 4.0), plus `5,12` if BY-SA is accepted. Treat id 7 ("No known copyright restrictions", Flickr Commons institutions) and id 8 with care. They are mostly historical archive photos, have low value for breed images, and are not a license grant in the same sense.
- Flickr needs your own API key (a request with a dummy key returned "Invalid API Key"). Flickr's own API terms, including any commercial-use limits on the API itself, were not reviewed. See Gaps.
- Openverse is the easiest single entry point, since it aggregates Flickr, Wikimedia and others with normalized license codes and attribution strings. The count of 240 is most likely an anonymous pagination cap, not the true total. Register for an API key (OAuth client credentials) to page further. This is unverified; check the Openverse API docs.
- Unsplash and Pexels: the license alone looks permissive, but the ToS govern site and API use. Unsplash's explicit ML-dataset ban and Pexels' ban on ML scraping and bulk copying mean both sites should be excluded unless the team gets written permission (Unsplash points to unsplash.com/data).
- iNaturalist is not useful for breeds: breed is not a taxon, and the domestic-dog breed hits are in single or double digits.
- A realistic target mix: Flickr/Openverse (CC0/PDM/BY) as the bulk source, Commons as a curated seed, plus the team's own photos (with owner consent) to fill the corgi and shiba gaps.

### Gaps
- Flickr API Terms of Use (commercial use of the API, rate limits) were not fetched. Check them before building a commercial pipeline on the Flickr API. Openverse is an alternative route to Flickr CC content.
- iNaturalist's default photo license and its terms on bulk download were not checked in this session.
- True Openverse totals per breed were not obtained (anonymous cap).

## Q5. Korean copyright law on TDM/AI training (as of Sept 2026)

### Takeaway
As of September 2026, Korea still has no enacted TDM exception. AI training has to rely on the general fair-use clause (제35조의5), which is judged case by case, or on licenses. MCST and the Korea Copyright Commission issued a non-binding generative-AI fair-use guide on 2026-02-26. The government has announced plans for an opt-out ("학습 거부 표시") system with "use first, compensate later" (선사용·후보상) through future amendments, but these were not law at research time. For this project, the safest basis is the licenses themselves (CC0/PD/BY), with fair use only as a backup.

### Cited Findings
- 저작권법 제35조의5 (fair use), text as in force from 2023-08-08: ① Outside the specific exceptions (제23조–제35조의4, 제101조의3–제101조의5), a work may be used where the use does not conflict with the normal exploitation of the work and does not unreasonably prejudice the author's legitimate interests. ② Factors: 1. purpose and character of use; 2. type and use of the work; 3. proportion and importance of the portion used; 4. effect on the current or potential market or value. — [casenote.kr 저작권법 제35조의5](https://casenote.kr/법령/저작권법/제35조의5)
- The current Act contains 제35조의2 (temporary reproduction) and 제35조의5 (fair use), neither specific to TDM. Korean TDM amendment bills (2020–2021 전부개정안 era) were drafted but not enacted. — [류시원, 법무부 논단 (moj.go.kr)](https://www.moj.go.kr/bbs/moj/166/450511/download.do); [KCI article](https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART002929583)
- MCST and the Korea Copyright Commission published 「생성형 인공지능의 저작물 학습에 대한 저작권법상 '공정이용' 안내서」 on 2026-02-26, after an Oct–Nov 2025 survey and a December public briefing. It explicitly says it is a reference document, not an authoritative interpretation, and that courts decide. — [Kim & Chang](https://www.kimchang.com/ko/insights/detail.kc?sch_section=4&idx=34407); [법률신문/화우](https://www.lawtimes.co.kr/news/articleView.html?idxno=217415); [MCST press (pre-release notice)](https://www.mcst.go.kr/site/s_notice/press/pressView.jsp?pSeq=22130)
- Per Kim & Chang's summary, the guide (82 pages) applies the four factors. Commercial purpose or web crawling does not automatically exclude fair use. Factors favoring fair use include training aimed at general capability rather than reproducing specific expression, technical measures that block identical or similar outputs, low-creativity source works, and no substitution of the originals' sales. Disfavoring factors include outputs substantially similar to the originals, highly creative sources, and market substitution or lost licensing opportunities. — [Kim & Chang](https://www.kimchang.com/ko/insights/detail.kc?sch_section=4&idx=34407)
- An English edition of the guide was released in May 2026. — [뉴스핌 2026-05-18](https://www.newspim.com/news/view/20260518000080); [아시아경제](https://view.asiae.co.kr/article/2026051723452713616)
- In March 2026, the government's plan for a "K-콘텐츠 AI 생태계" included activating an AI training-refusal marking (opt-out) system and, where rights holders are unclear or no refusal was marked, permitting training with later compensation or revenue sharing, through "copyright law amendments" and standard AI-training license contracts. No implementation date was given. — [다음/뉴스 2026-03-11](https://v.daum.net/v/20260311150659807)
- A late-2025 opinion piece discussed a TDM-style copyright amendment for AI training debated in the Democratic Party's copyright committee, noting opposition from rights holders. — [한겨레 왜냐면 via 네이트 2025-12-31](https://m.news.nate.com/view/20251231n26249)
- In January 2025 MCST said it would pursue an amendment requiring disclosure of AI training data lists. (Reported in a search-result summary; the primary press release was not fetched.) — [Lexology summary](https://www.lexology.com/library/detail.aspx?g=37653697-b80e-4811-be57-0072b6dc7529)
- The government was reported (2026-02-27) to be reviewing exemption from criminal copyright liability for the national "국가대표 AI" project (headline only). — [머니투데이](https://www.mt.co.kr/tech/2026/02/27/2026022617245582282)
- Earlier guidance: the 2023 「생성형 AI 저작권 안내서」 exists (MCST/KCC, Dec 2023). — [국회도서관 국가전략포털](https://nsp.nanet.go.kr/plan/subject/detail.do?nationalPlanControlNo=PLAN0000043860)
- A critique of the 2026 guide's significance and limits is available from KISO. — [KISO저널](https://journal.kiso.or.kr/?p=13789)
- Comparative: the UK (2014), Germany (2017) and Japan (2018) each added a specific TDM exception to their statutes. Commentators note that Japan and Singapore apply theirs under strict conditions. — [Lexology/Nepla summaries via search](https://www.nepla.ai/wiki/%EC%A7%80%EC%8B%9D%EC%9E%AC%EC%82%B0/%EC%A0%80%EC%9E%91%EA%B6%8C/ai-%ED%95%99%EC%8A%B5%EB%8D%B0%EC%9D%B4%ED%84%B0-%EC%A0%80%EC%9E%91%EA%B6%8C-%EC%B9%A8%ED%95%B4%EC%99%80-%EC%A0%80%EC%9E%91%EA%B6%8C%EB%B2%95-%EC%83%81%EC%9D%98-tdm-%EC%A1%B0%ED%95%AD-%EB%8F%84%EC%9E%85-%EB%85%BC%EC%9D%98-zr592w2dv96k)
- A German case (Hamburg Regional Court) interpreted AI-training opt-out under the EU TDM regime. — [KOCCA 평석](https://welcon.kocca.kr/ko/info/trend/1956275)

### Inferences
- There is no statutory TDM safe harbor in Korea as of 2026-09, so a small team should not rely on fair use as its primary basis. Relying on the licenses (CC0/PDM/BY) means CC's grant covers the use whether or not fair use applies. CC also notes its license terms simply do not apply where an exception does.
- If fair use were argued, a breed classifier is in a relatively good position under the four factors. It produces labels, not images, so there is no substitution of the photos' market and no similar outputs. The photos are used only to learn visual features. But the MCST guide targets generative AI and, per the summary, does not discuss classifiers, so this is an analogy, not official guidance.
- A future opt-out regime would matter mainly for scraped, unlicensed content. For CC-licensed material, the license already grants permission. Still, record the retrieval date and honor any "no AI training" marks or robots/TDM-reservation signals as good practice.
- US/EU notes (where Korean law is silent): in the EU, the DSM Directive Art. 4 TDM exception allows commercial TDM unless rights are reserved in machine-readable form, which is why opt-out handling matters there. In the US, it is a fair-use analysis. (Based on background knowledge; the KOCCA note above covers the EU opt-out case law. Primary texts were not fetched here.)

### Gaps
- I could not retrieve law.go.kr pages directly. Article text came from casenote.kr, a secondary mirror of the statute.
- I found no confirmed bill number or 2026 committee status for a specific TDM amendment. Reports describe plans and debates, not an enacted provision.
- The full text of the 2026 fair-use guide was not read, only law-firm and news summaries. In particular, it is unverified whether the guide discusses lawful access, robots.txt or opt-out, or non-generative models.
- 제37조 (출처 명시) obligations when relying on exceptions were not checked.

## Q6. Risks: mislabeled breeds, duplicates, people in photos, watermarks

### Takeaway
The main data-quality risks are wrong or loose breed tags, mixes and hybrids, the same photo copied across Flickr, Commons and Openverse, identifiable people, and watermarks or text overlays. People in photos are also a legal risk: Unsplash's terms even name person-identification technology. All of these can be handled with a cheap automated filter followed by a manual review pass.

### Cited Findings
- Commons breed categories include hybrid, art, skeleton, scarecrow and individual-famous-dog subcategories next to real breed photos (e.g. "Golden Retriever hybrids", "Siberian-Askal", "Scarecrows of Welsh Corgi", "Kabosu (dog)"). — [Commons API subcats](https://commons.wikimedia.org/w/api.php?action=query&list=categorymembers&cmtitle=Category:Welsh_Corgi&cmtype=subcat&cmlimit=50&format=json)
- A 200-file Commons sample contained non-JPEG and non-image files (9 PNG, 1 Ogg). — [Commons API](https://commons.wikimedia.org/w/api.php?action=query&generator=categorymembers&gcmtitle=Category:Shiba_Inu&gcmtype=file&gcmlimit=200&prop=imageinfo&iiprop=extmetadata|mime&iiextmetadatafilter=LicenseShortName&format=json)
- Openverse aggregates Flickr and other sources, so the same image can surface through several routes (the Shiba top hit had source = flickr). — [Openverse API](https://api.openverse.org/v1/images/?q=shiba%20inu&license=by,cc0,pdm,by-sa&page_size=1)
- Unsplash Terms separately prohibit use "for technologies designed or intended for the identification of natural persons." — [Unsplash Terms](https://unsplash.com/terms)

### Inferences
- Mislabels: free-text Flickr tags like "husky" often mean Alaskan huskies or malamutes, and "corgi" mixes Pembroke and Cardigan. Mitigations:
  - Require the breed term in the title or tags and pick specific terms ("siberian husky", "shiba inu").
  - Pre-score with an ImageNet or Stanford Dogs pretrained model, which already has these breeds, and send low-confidence or disagreeing cases to manual review.
  - Audit at least a random 5–10% per class.
- Duplicates: dedup on source ID, then SHA-1, then perceptual hash (pHash/dHash, Hamming distance ≤ 6–8), and also across the train/test split so that crops and resizes of the same photo do not leak. Keep all attributions for merged duplicates.
- People and privacy: Korea's 개인정보 보호법 treats identifiable faces as personal information. Run a person/face detector and either drop those images or crop to the dog. The model only needs dog pixels, and this also avoids the "identification of natural persons" concern.
- Watermarks and overlays: run an OCR or text detector and a watermark classifier, or drop images with large text regions. Watermarks also hint that the upload may not be the original author's, meaning possible license laundering. Prefer uploads whose author matches the account.
- License laundering in general: a CC tag on Flickr or Commons is only as good as the uploader. Keep the manifest, respond to takedowns, and retrain without removed images if needed.

### Gaps
- No published measurements of breed-label noise rates on Flickr or Commons were found in this session.
- The Korean PIPC guidance on processing publicly available personal data for AI (2024) was not fetched. Check it if photos with people are kept.
