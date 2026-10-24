# 图片生成提示词

生成方式：内置 image_gen，以此前虚构病例为版式与患者连续性参考，再加入中等强度折痕及不均匀光照。

## 06_mushroom_20260924_crossfold_shadow

Use case: photorealistic-natural
Asset type: moderately challenging smartphone photo of a fictional outpatient chart for OCR testing.
Input image 1: layout/typography and patient continuity reference ONLY. Keep this exact fixed LANDSCAPE hospital template, centered title "北京中医药大学东直门医院国际部门诊病历", two demographic rows separated by thin rules, fixed narrow left label column, Song/Ming black print, wrapped body aligned to same tab stop, multi-column Chinese herb doses, page/physician footer. Create a NEW visit of the SAME fictional patient "测试小蘑菇", female, age 66, with exact new date and content below, NOT the old date/content.
MAIN REQUEST: the reference looks too pristine and evenly lit. Make this a SIGNIFICANTLY LESS IDEAL but still usable real phone photograph, moderate OCR difficulty. It must immediately look more difficult than reference when viewed as a thumbnail. Do not output a clean scan or beauty product photo.
Physical/light conditions: 明显十字折痕，反复折过后重新展开，中央折交处轻微凸起；折沟两侧有清晰可见的亮边和窄深阴影，正文随折痕有小幅弯曲。下午窗边侧光从左上照射，右下约三分之一纸面明显较暗，比亮部低约1.5至2档曝光。整张纸斜放约6度，手机随手拍，边缘略软，纸角完整。中等难度，明显比参考图光照不均和褶皱更重。
Make fold creases physically conspicuous: compressed fold ridges and valleys several millimeters wide, brighter raised edges and dark narrow side shadows that interrupt local text baselines slightly. A broad natural diagonal side shadow crosses the document, with bright white region versus visibly gray, roughly two-stops-darker region. Keep genuine paper fiber, slight waviness, mildly reduced camera sharpness and subtle sensor grain, especially near far corners. Printed letters are not artificially redrawn with perfect sharpness. The shadow is TRANSLUCENT LIGHTING, not an object or black rectangle.
Limits: the doctor must still be able to read all words at full size; no portions missing, no tears, no occlusion, no blacked-out text, no fingers, pens, objects on page, no clipped highlights washing away ink, no extreme blur or extreme crumpling. Show full sheet/all corners with narrow tabletop background; upright landscape approximately 2048x1536. Do not sacrifice the hospital format. Small footer marker "虚构测试样例 06 · 非真实就诊记录", not a large overlay.
Exact NEW text (replace reference clinical text; preserve dates, numbers, units and uncertainty markers; no omissions):
北京中医药大学东直门医院国际部门诊病历
就诊时间：2026-09-24 09:36:18    就诊科室：国际部脾胃病科一区门诊
姓名：测试小蘑菇    性别：女    年龄：66岁    门诊号：TEST-20261010-003
主诉：反复上腹隐痛、早饱2年，携胃镜病理结果复诊。
现病史：近2个月餐后上腹饱胀，进食量较前减少，疼痛间断发作。无呕血、黑便及明显消瘦。此次主要核对病理取材部位，过去检查原件未带齐。
2026-09-12胃镜：胃窦黏膜红白相间，局部血管纹理可见。病理部位：胃窦小弯、胃窦大弯、胃角。病理诊断：胃窦小弯慢性萎缩性胃炎，轻度肠上皮化生；胃角慢性炎症，未见异型增生。幽门螺杆菌：本次病理染色阴性，既往根除治疗史不详。
既往史：高血压8年，口服氨氯地平5mg，每日1次；胆囊切除术后6年。个人史：不吸烟、不饮酒。过敏史：头孢类药物用后皮疹，具体品种不详。家族史：父亲70岁时诊断胃癌。
中医四诊：舌淡红，苔薄，脉细。
生命体征：血压140/84mmHg，脉搏76次/分；腹软，剑突下轻压痛，无反跳痛。
西医诊断：慢性萎缩性胃炎伴肠上皮化生；高血压病史。
中医诊断：胃痞病：气阴不足证。
药品处方：瑞巴派特片100mg，口服，每日3次，共14天。既往降压药按原处方继续，本次未调整。
中药配方：P太子参15g　P茯苓12g　P炒白术12g　P麦冬9g
P白芍12g　P陈皮6g　P炙甘草3g
中药7付，每天一剂，水煎服，分2次口服。
建议：记录腹痛、早饱和体重变化；补充既往胃镜、病理原件。后续复查计划由接诊医生核对完整资料后确认。
（以下空白）
第1页/共1页    门诊医生：模拟医生丙
虚构测试样例 06 · 非真实就诊记录

## 07_mushroom_20261015_accordion_side_light

Use case: photorealistic-natural
Asset: a NEW moderately challenging smartphone photo of a fictional outpatient paper record for OCR testing.
Input image 1 = layout/typography + the correct fictional patient's longitudinal identity/history reference.
Input image 2 = TARGET DIFFICULTY reference ONLY: stronger fold ridges, obvious nonuniform light, gray shadow zones and ordinary phone photo look. Never copy its old text if different from the exact new case below.
Keep EXACT fixed landscape hospital template from image 1: centered title "北京中医药大学东直门医院国际部门诊病历", two demographic rows between thin rules, left fixed labels 主诉/现病史/既往史/中医四诊/生命体征/西医诊断/中医诊断/药品处方/中药配方/建议, Song/Ming Chinese print, consistent body tab stops, multi-column herb entries, lower whitespace and footer.
New patient = 测试小蘑菇, 女, age 66; new visit date = 2026-10-15 14:22:31; outpatient number = TEST-20261010-003. Replace ALL clinical text with specified new visit. Preserve exact patient identity. Do not copy other patient's demographics or old visit date from either image.
USER REQUEST IS STRONGER PHOTO DIFFICULTY: make folds and shadows immediately apparent and at least as substantial as image 2. This should look like an imperfect phone snapshot, not evenly illuminated scanner output. Full detailed scene: 纸张曾折成三折后展开，两条横向折线和一条浅竖折清楚可见，形成缓缓起伏的纸面。用室内顶灯加窗边光拍摄，纸面上半部偏冷白，下半部暖灰，中央有宽而柔的斜向阴影，暗区仍能人工逐字阅读。相机略从左侧俯拍，透视差约8度，轻微手机边缘柔焦。折痕纹理和明暗差应明显强于参考图，而非几乎平整的扫描图。
Fold bands must visibly bend/bulge the paper and subtly distort nearby text baselines. Broad real lighting shadows should visibly darken meaningful portions of the text to light/medium gray, about 1.5–2 exposure stops below the brightest region. Include slight paper waviness, mild corner softness and realistic phone noise. Maintain human readability, but do NOT reconstruct a pristine crisp flat poster. Avoid repeating the exact same crease/shadow pattern from image 2.
Bounds: whole A4 landscape sheet/all corners visible with narrow tabletop background, upright reading orientation, approximately 2048x1536. No tears, missing portions, covering objects, hands, pens, clips, blackout, opaque shadows or highlights removing letters; no extreme blur. No real signature. Small footer corner "虚构测试样例 07 · 非真实就诊记录", no large watermark over body.
Print exact NEW text faithfully, preserving all numbers, negatives, unknown statements and diagnostic question marks. Keep all sections on one page; no collage:
北京中医药大学东直门医院国际部门诊病历
就诊时间：2026-10-15 14:22:31    就诊科室：国际部脾胃病科一区门诊
姓名：测试小蘑菇    性别：女    年龄：66岁    门诊号：TEST-20261010-003
主诉：胃病复诊，上腹不适较前减轻，仍有早饱。
现病史：2026-10-10复诊后按处方服药，腹痛次数较前减少，晚餐稍多仍有胃胀。近5天未出现黑便、呕吐，体重无明显变化。中药已服5付，尚余2付；具体症状评分未记录。
既往2026-09-12病理提示胃窦小弯轻度肠上皮化生，未见异型增生。本次未做新的胃镜或病理检查。幽门螺杆菌：原病理染色阴性，既往治疗史仍待核实。
既往史：高血压8年，口服氨氯地平5mg，每日1次；胆囊切除术后6年。个人史：不吸烟、不饮酒。过敏史：头孢类药物用后皮疹，具体品种不详。家族史：父亲70岁时诊断胃癌。
中医四诊：舌淡红，苔薄白，脉细。
生命体征：血压134/78mmHg，脉搏74次/分；腹软，上腹轻压痛较前减轻，无反跳痛。
西医诊断：慢性萎缩性胃炎伴肠上皮化生（既往病理）；本次无新增病理结论。
中医诊断：胃痞病：气阴不足证。
药品处方：瑞巴派特片按上次100mg、每日3次的处方完成原疗程，本次不重复开具。继续原有降压治疗。
中药配方：上次中药7付已服5付，尚余2付。本次未新增药味或剂量，原方见2026-10-10处方。
建议：规律进餐，携历次胃镜、病理原件复诊，记录近期腹痛与早饱变化。
（以下空白）
第1页/共1页    门诊医生：模拟医生丙
虚构测试样例 07 · 非真实就诊记录

## 08_mushroom_20261020_diagonal_fold_mixed_light

Use case: photorealistic-natural
Asset: a NEW moderately challenging smartphone photo of a fictional outpatient paper record for OCR testing.
Input image 1 = layout/typography + the correct fictional patient's longitudinal identity/history reference.
Input image 2 = TARGET DIFFICULTY reference ONLY: stronger fold ridges, obvious nonuniform light, gray shadow zones and ordinary phone photo look. Never copy its old text if different from the exact new case below.
Keep EXACT fixed landscape hospital template from image 1: centered title "北京中医药大学东直门医院国际部门诊病历", two demographic rows between thin rules, left fixed labels 主诉/现病史/既往史/中医四诊/生命体征/西医诊断/中医诊断/药品处方/中药配方/建议, Song/Ming Chinese print, consistent body tab stops, multi-column herb entries, lower whitespace and footer.
New patient = 测试小蘑菇, 女, age 66; new visit date = 2026-10-20 10:08:47; outpatient number = TEST-20261010-003. Replace ALL clinical text with specified new visit. Preserve exact patient identity. Do not copy other patient's demographics or old visit date from either image.
USER REQUEST IS STRONGER PHOTO DIFFICULTY: make folds and shadows immediately apparent and at least as substantial as image 2. This should look like an imperfect phone snapshot, not evenly illuminated scanner output. Full detailed scene: 明显斜折线从左上中部延伸至右下，另有一条横向旧折痕，纸面有几处较浅波浪褶皱，不是揉烂。左侧偏暖日光、右侧偏冷环境光，形成明显宽幅亮暗过渡；右侧正文区比左侧暗约2档但不发黑，亮区不曝光成纯白。手机斜拍约10度，完整纸边都在画面内，微弱边角柔焦。中等困难、文字最终仍可由医生读出。
Fold bands must visibly bend/bulge the paper and subtly distort nearby text baselines. Broad real lighting shadows should visibly darken meaningful portions of the text to light/medium gray, about 1.5–2 exposure stops below the brightest region. Include slight paper waviness, mild corner softness and realistic phone noise. Maintain human readability, but do NOT reconstruct a pristine crisp flat poster. Avoid repeating the exact same crease/shadow pattern from image 2.
Bounds: whole A4 landscape sheet/all corners visible with narrow tabletop background, upright reading orientation, approximately 2048x1536. No tears, missing portions, covering objects, hands, pens, clips, blackout, opaque shadows or highlights removing letters; no extreme blur. No real signature. Small footer corner "虚构测试样例 08 · 非真实就诊记录", no large watermark over body.
Print exact NEW text faithfully, preserving all numbers, negatives, unknown statements and diagnostic question marks. Keep all sections on one page; no collage:
北京中医药大学东直门医院国际部门诊病历
就诊时间：2026-10-20 10:08:47    就诊科室：国际部脾胃病科一区门诊
姓名：测试小蘑菇    性别：女    年龄：66岁    门诊号：TEST-20261010-003
主诉：慢性胃炎复诊，餐后饱胀较前减轻。
现病史：近期腹痛很少发作，早饱仍间断出现。已服完上次7付中药，未诉明显用药不适。无黑便、进行性消瘦或吞咽困难。此次补交一份旧病理复印件，但部分取材部位文字较淡，需对照原件核对。
2026-09-12病理所述胃窦小弯轻度肠化保留记录；其他部位是否肠化待逐项核对，不默认全部阴性。本次未复查胃镜。
既往史：高血压8年，口服氨氯地平5mg，每日1次；胆囊切除术后6年。个人史：不吸烟、不饮酒。过敏史：头孢类药物用后皮疹，具体品种不详。家族史：父亲70岁时诊断胃癌。
中医四诊：舌淡红，苔薄，脉细。
生命体征：血压130/80mmHg，脉搏72次/分；腹软，无明显压痛，无反跳痛。
西医诊断：慢性萎缩性胃炎伴肠上皮化生（胃窦小弯，既往病理）。
中医诊断：胃痞病：证候随访核对。
药品处方：原瑞巴派特疗程尚未结束，按原处方继续，本次未重复开具西药；降压药未调整。
中药配方：P太子参15g　P茯苓12g　P炒白术12g　P麦冬9g
P白芍12g　P陈皮6g　P炙甘草3g
中药7付，每天一剂，水煎服，分2次口服。
建议：携原病理报告与新补复印件核对；记录症状及用药情况，后续随访安排由接诊医生确认。
（以下空白）
第1页/共1页    门诊医生：模拟医生丙
虚构测试样例 08 · 非真实就诊记录

## 09_bread_20261020_doublefold_window_shadow

Use case: photorealistic-natural
Asset: a NEW moderately challenging smartphone photo of a fictional outpatient paper record for OCR testing.
Input image 1 = layout/typography + the correct fictional patient's longitudinal identity/history reference.
Input image 2 = TARGET DIFFICULTY reference ONLY: stronger fold ridges, obvious nonuniform light, gray shadow zones and ordinary phone photo look. Never copy its old text if different from the exact new case below.
Keep EXACT fixed landscape hospital template from image 1: centered title "北京中医药大学东直门医院国际部门诊病历", two demographic rows between thin rules, left fixed labels 主诉/现病史/既往史/中医四诊/生命体征/西医诊断/中医诊断/药品处方/中药配方/建议, Song/Ming Chinese print, consistent body tab stops, multi-column herb entries, lower whitespace and footer.
New patient = 测试小面包, 女, age 58; new visit date = 2026-10-20 11:35:09; outpatient number = TEST-20261019-005. Replace ALL clinical text with specified new visit. Preserve exact patient identity. Do not copy other patient's demographics or old visit date from either image.
USER REQUEST IS STRONGER PHOTO DIFFICULTY: make folds and shadows immediately apparent and at least as substantial as image 2. This should look like an imperfect phone snapshot, not evenly illuminated scanner output. Full detailed scene: 两条明显横折和较浅竖折，纸面展开后有真实折脊、浅凹沟与细微起伏。窗边阳光在纸面形成一条宽斜向光带，左上明显较亮、右下阴影显著；亮部不冲掉黑字，暗部不变成黑块。约7度透视，白平衡偏暖，像患者用普通手机随手拍摄，有轻微边缘锐度下降。所有文字仍可人工阅读，没有物品盖纸。
Fold bands must visibly bend/bulge the paper and subtly distort nearby text baselines. Broad real lighting shadows should visibly darken meaningful portions of the text to light/medium gray, about 1.5–2 exposure stops below the brightest region. Include slight paper waviness, mild corner softness and realistic phone noise. Maintain human readability, but do NOT reconstruct a pristine crisp flat poster. Avoid repeating the exact same crease/shadow pattern from image 2.
Bounds: whole A4 landscape sheet/all corners visible with narrow tabletop background, upright reading orientation, approximately 2048x1536. No tears, missing portions, covering objects, hands, pens, clips, blackout, opaque shadows or highlights removing letters; no extreme blur. No real signature. Small footer corner "虚构测试样例 09 · 非真实就诊记录", no large watermark over body.
Print exact NEW text faithfully, preserving all numbers, negatives, unknown statements and diagnostic question marks. Keep all sections on one page; no collage:
北京中医药大学东直门医院国际部门诊病历
就诊时间：2026-10-20 11:35:09    就诊科室：国际部脾胃病科一区门诊
姓名：测试小面包    性别：女    年龄：58岁    门诊号：TEST-20261019-005
主诉：补充外院用药资料，核对幽门螺杆菌治疗后复查安排。
现病史：昨日复诊后找到部分外院处方，今日补交。2026-08-30呼气试验阳性，曾完成含铋四联治疗14天；处方复印件中两种药的用法文字较淡，仍需核对。现偶有餐后腹胀，无持续腹痛、呕血或黑便。
幽门螺杆菌：治疗前阳性，治疗后尚未复查，不能判定已根除。病理诊断：原报告只写慢性胃炎，萎缩程度及肠上皮化生情况未知，待补完整原件。
既往史：2型糖尿病5年，口服二甲双胍500mg，每日2次；脂肪肝3年。过敏史：磺胺类药物过敏；青霉素过敏史未核实。个人史：不吸烟、不饮酒。家族史：姐姐曾感染幽门螺杆菌，胃癌家族史未提供。
中医四诊：舌淡红，苔薄腻，脉滑。
生命体征：血压126/78mmHg，脉搏78次/分；腹软，无明显压痛。
西医诊断：幽门螺杆菌感染治疗后，根除结果待确认；慢性胃炎；2型糖尿病病史。
中医诊断：胃痞病：证候待确认。
药品处方：本次未重复开具抗菌药；继续既往糖尿病治疗，本次未调整。既往抗菌药名、剂量及近期抑酸药停用情况待核对。
中药配方：本次未开具中药处方。
建议：核对外院用药与近期抑酸药使用，再由接诊医生确定呼气试验复查安排；本次未作根除成功判定。
（以下空白）
第1页/共1页    门诊医生：模拟医生戊
虚构测试样例 09 · 非真实就诊记录

## 10_kelp_20261020_wrinkles_side_shadow

Use case: photorealistic-natural
Asset: a NEW moderately challenging smartphone photo of a fictional outpatient paper record for OCR testing.
Input image 1 = layout/typography + the correct fictional patient's longitudinal identity/history reference.
Input image 2 = TARGET DIFFICULTY reference ONLY: stronger fold ridges, obvious nonuniform light, gray shadow zones and ordinary phone photo look. Never copy its old text if different from the exact new case below.
Keep EXACT fixed landscape hospital template from image 1: centered title "北京中医药大学东直门医院国际部门诊病历", two demographic rows between thin rules, left fixed labels 主诉/现病史/既往史/中医四诊/生命体征/西医诊断/中医诊断/药品处方/中药配方/建议, Song/Ming Chinese print, consistent body tab stops, multi-column herb entries, lower whitespace and footer.
New patient = 假人小海带, 男, age 29; new visit date = 2026-10-20 15:16:42; outpatient number = TEST-20261015-004. Replace ALL clinical text with specified new visit. Preserve exact patient identity. Do not copy other patient's demographics or old visit date from either image.
USER REQUEST IS STRONGER PHOTO DIFFICULTY: make folds and shadows immediately apparent and at least as substantial as image 2. This should look like an imperfect phone snapshot, not evenly illuminated scanner output. Full detailed scene: 纸张有明显的十字旧折痕及三四条自然细褶，底边轻微卷曲，但没有折角盖住正文。室内偏暗环境，右上来光，左侧和中下部有较大范围柔阴影；阴影内的字对比度降低但仍能辨认。手机约9度斜拍，轻度拍照噪点和边缘柔焦，不要锐利如扫描件，也不要严重失焦。全张纸完整且不被手、笔、夹子遮挡。
Fold bands must visibly bend/bulge the paper and subtly distort nearby text baselines. Broad real lighting shadows should visibly darken meaningful portions of the text to light/medium gray, about 1.5–2 exposure stops below the brightest region. Include slight paper waviness, mild corner softness and realistic phone noise. Maintain human readability, but do NOT reconstruct a pristine crisp flat poster. Avoid repeating the exact same crease/shadow pattern from image 2.
Bounds: whole A4 landscape sheet/all corners visible with narrow tabletop background, upright reading orientation, approximately 2048x1536. No tears, missing portions, covering objects, hands, pens, clips, blackout, opaque shadows or highlights removing letters; no extreme blur. No real signature. Small footer corner "虚构测试样例 10 · 非真实就诊记录", no large watermark over body.
Print exact NEW text faithfully, preserving all numbers, negatives, unknown statements and diagnostic question marks. Keep all sections on one page; no collage:
北京中医药大学东直门医院国际部门诊病历
就诊时间：2026-10-20 15:16:42    就诊科室：国际部脾胃病科一区门诊
姓名：假人小海带    性别：男    年龄：29岁    门诊号：TEST-20261015-004
主诉：腹痛伴便次增多复诊，症状较前减轻。
现病史：2026-10-15就诊后开始记录便形并服中药5付，大便现每日1至2次，多为软便；紧张时仍有脐周不适，排便后可缓解。无肉眼血便、夜间腹泻及发热，体重稳定。
补交2026-08-22肠镜报告，未见明显器质性病变，但未提供活检结果。2026-10-08血红蛋白145g/L、C反应蛋白2.1mg/L、大便隐血阴性。本次未做新的肠镜或实验室检查。
既往史：无明确慢性病史；1年前曾有急性胃肠炎，否认肠道手术史。过敏史：无已知药物过敏，饮牛奶后易腹胀。个人史：久坐、咖啡饮用较多，近期减少熬夜。家族史：否认已知炎症性肠病家族史，其他家族史未提供。
中医四诊：舌淡红，苔薄白，脉弦。
生命体征：血压116/70mmHg，脉搏74次/分；腹软，左下腹轻压痛较前减轻，无反跳痛。
西医诊断：功能性肠病待评估；肠易激综合征？（腹泻型，诊断待完整资料核对）。
中医诊断：泄泻病：肝郁脾虚证。
药品处方：本次未开具西药。既往蒙脱石散为自行间断使用，用法仍不详。
中药配方：上次中药7付已服5付，尚余2付，本次未新增处方。
原方：P炒白术12g　P白芍12g　P防风6g　P陈皮6g
P山药15g　P茯苓12g　P炙甘草3g
建议：继续记录每日便次、便形、腹痛频率和诱发食物；完善未提供的检查资料，2周后复诊。
（以下空白）
第1页/共1页    门诊医生：模拟医生丁
虚构测试样例 10 · 非真实就诊记录