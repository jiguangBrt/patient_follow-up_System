# 图片生成提示词

生成方式：内置 image_gen。先根据用户提供的格式参考生成医院模板版，再以首张虚构病例作为其余图片的版式参考。

## 01_clear_gastritis

Use case: photorealistic-natural
Asset: one landscape Chinese outpatient chart photo for OCR testing.
Input image 1 is ONLY A FORMAT AND TYPOGRAPHY REFERENCE. The original photo is rotated sideways: imagine rotating it 90 degrees counterclockwise to read upright. Match that actual hospital's fixed LANDSCAPE outpatient paper format extremely closely: horizontal A4 single sheet, centered title "北京中医药大学东直门医院国际部门诊病历", thin rule above the demographic area and thin rule below it, first row encounter date/time on left and department on right, second row name on left followed by sex, age, outpatient number. Under the rules the fixed narrow left label column is 主诉、现病史、既往史、中医四诊、生命体征、西医诊断、中医诊断、药品处方、中药配方、建议. Content starts at a consistent tab to the right and wraps across the wide landscape page. Use plain authentic black Chinese Song/Ming text and spacing similar to reference, no modern UI cards or new section dividers. Prescription of Chinese herbs arranged across several aligned columns like the reference. Footer: page count near lower middle-left and physician near lower right, ample blank lower area, （以下空白） below advice.
Create an ENTIRELY NEW FICTIONAL CHART. Do NOT copy original patient's name, demographics, numbers, clinical facts or original doctor's handwriting/signatures. Replace ALL patient/clinical content with exact text specified below. Keep only the template and public hospital title. Printed simulated doctor's name only, no forged signatures.
Return in UPRIGHT LANDSCAPE orientation, around 2048x1536 or larger. Entire page with all edges visible and narrow background margin. 清晰基准图。完整平整的白色A4病历放在浅灰色桌面上，正上方拍摄，均匀自然光，无折痕。 The photo should look like an ordinary printout of the same software-generated hospital template, not a redesigned document. Tiny unobtrusive footer corner "虚构测试样例 01 · 非真实就诊记录" must remain readable, with no watermark over clinical text.
Exact text, preserve every medical uncertainty marker and all negative/unknown distinctions, do not summarize:
北京中医药大学东直门医院国际部门诊病历
就诊时间：2026-10-01 09:18:26    就诊科室：国际部脾胃病科一区门诊
姓名：测试小土豆    性别：女    年龄：53岁    门诊号：TEST-20261001-001
主诉：反复上腹胀痛6个月，加重1周。
现病史：餐后上腹饱胀，偶有嗳气，少量反酸。进食过快后明显，休息后可缓解。近1周外出聚餐后症状加重。无呕血、黑便、吞咽困难，体重近半年基本稳定。
胃镜所见：2026-09-18胃窦黏膜散在充血、水肿，未见溃疡及新生物。 病理部位：胃窦。 病理诊断：慢性非萎缩性胃炎，轻度活动；未见肠上皮化生。 幽门螺杆菌：2026-09-20呼气试验阴性。
既往史：慢性胃炎3年；否认胃部手术史。2025年曾口服抑酸药后好转，具体疗程记不清。 个人史：不吸烟，偶饮酒；工作日三餐不定时，喜浓茶。 过敏史：否认已知药物过敏。 家族史：父亲有胃溃疡病史；胃癌家族史未提供。
中医四诊：舌淡红，苔薄白，脉细。
生命体征：血压126/78mmHg，脉搏76次/分；腹软，上腹轻压痛，无反跳痛。
西医诊断：慢性非萎缩性胃炎；消化不良。
中医诊断：胃痞病：脾胃气虚证（模拟记录）。
药品处方：奥美拉唑肠溶胶囊20mg，口服，每日1次，共14天；瑞巴派特片100mg，口服，每日3次，共14天。
中药配方：P党参9g　P茯苓12g　P炒白术9g　P陈皮6g
P法半夏9g　P炙甘草3g　P木香6g　P砂仁3g（后下）
中药7付，每天一剂，水煎服，分2次口服。
建议：规律进餐，记录症状与食物关系；2周后复诊，携带既往检查原件。
（以下空白）
第1页/共1页    门诊医生：模拟医生甲
虚构测试样例 01 · 非真实就诊记录
Constraints: one page, one image; readable dense text; full original-style left label structure; do not introduce a separate cover page or second poster; no damage/obstruction; no real patient data from reference.

## 02_vertical_fold_reflux

Use case: photorealistic-natural
Asset: one horizontal outpatient medical chart photo for OCR software testing.
Input image 1 is a FICTIONAL LAYOUT REFERENCE ONLY. Keep its EXACT hospital document template, landscape A4 orientation, title typography and placement, the two demographic rows between thin horizontal rules, narrow left section-label column, matching tab stops, multi-column herb prescription, lower blank area, （以下空白）, page count and physician footer. Title verbatim "北京中医药大学东直门医院国际部门诊病历". Department verbatim "国际部脾胃病科一区门诊". All left fixed labels in same order as reference: 主诉、现病史、既往史、中医四诊、生命体征、西医诊断、中医诊断、药品处方、中药配方、建议. Extra history and test information wraps in the existing right-hand content area, not new large section boxes.
Replace EVERY patient/clinical item from input with the exact new fictional case below; do not retain the reference patient's name, dates, age, numbers, diagnosis or drugs.
Photo scene and mild difficulty: 轻度困难图。完整白色A4纸有一条轻微竖向折痕，已充分展开摊平，折痕仅产生细浅阴影、不挡字；纸张顺时针斜放约5度，轻微自然透视。浅木色桌面，柔和日光，所有正文可读。
Output in upright LANDSCAPE around 2048x1536 or greater. Fit all specified text on one full sheet using realistic black Chinese Song/Ming print of roughly the same size as reference. All page edges visible, enough margin so perspective never crops corners. Natural paper lighting and texture, text fully readable; no severe wrinkles/blur. Put unobtrusive small footer-corner "虚构测试样例 02 · 非真实就诊记录". NO new disclaimer heading, NO red stamp, NO logo, NO watermark across the body. This is a fictional test record, with printed simulated doctor's name, never imitate a real signature.
Exact complete text, do not paraphrase or omit, preserve diagnostic question marks and distinctions between negative/unknown/not performed:
北京中医药大学东直门医院国际部门诊病历
就诊时间：2026-10-05 14:06:12    就诊科室：国际部脾胃病科一区门诊
姓名：虚构小南瓜    性别：男    年龄：41岁    门诊号：TEST-20261005-002
主诉：反酸、烧心3个月，夜间加重2周。
现病史：胸骨后烧灼感，伴酸水上涌，晚餐过饱及平卧时明显。偶有咽部异物感，无进行性吞咽困难，无呕血、黑便。自行间断服抑酸药后症状可减轻，停药后反复。
胃镜所见：2026-09-26食管下段见两处长度约3mm黏膜破损；胃窦轻度充血。 胃镜诊断：反流性食管炎（LA-A级）；慢性胃炎。 病理诊断：本次未取活检，病理结果未知。 幽门螺杆菌：未提供既往检测结果，待核对。
既往史：高脂血症2年，具体用药未提供；否认糖尿病及消化道手术史。 个人史：吸烟约10支/日，持续15年；每周饮啤酒1至2次，常吃夜宵。 过敏史：青霉素用药后曾出现皮疹，时间不详。 家族史：母亲有反流症状，未提供检查结果。
中医四诊：舌红，苔薄黄，脉弦。
生命体征：血压132/84mmHg，脉搏82次/分；腹软，无明显压痛。
西医诊断：胃食管反流病；反流性食管炎。
中医诊断：吐酸病：证候待进一步辨证。
药品处方：埃索美拉唑镁肠溶片20mg，口服，每日1次，共28天；铝碳酸镁咀嚼片0.5g，口服，每次1片，必要时使用。
中药配方：本次未开具中药处方。
建议：记录夜间反流频次；减少夜宵及饮酒，餐后避免立即平卧；4周后复诊。
（以下空白）
第1页/共1页    门诊医生：模拟医生乙
虚构测试样例 02 · 非真实就诊记录
Constraints: patient name exactly "虚构小南瓜". Exactly one photographed page, no collage or extra panels. Do not reuse reference case's content. No hands, paperweights, pens, covering objects, tears, damage, stains obscuring text, missing areas or illegible handwriting.

## 03_cross_fold_metaplasia

Use case: photorealistic-natural
Asset: one horizontal outpatient medical chart photo for OCR software testing.
Input image 1 is a FICTIONAL LAYOUT REFERENCE ONLY. Keep its EXACT hospital document template, landscape A4 orientation, title typography and placement, the two demographic rows between thin horizontal rules, narrow left section-label column, matching tab stops, multi-column herb prescription, lower blank area, （以下空白）, page count and physician footer. Title verbatim "北京中医药大学东直门医院国际部门诊病历". Department verbatim "国际部脾胃病科一区门诊". All left fixed labels in same order as reference: 主诉、现病史、既往史、中医四诊、生命体征、西医诊断、中医诊断、药品处方、中药配方、建议. Extra history and test information wraps in the existing right-hand content area, not new large section boxes.
Replace EVERY patient/clinical item from input with the exact new fictional case below; do not retain the reference patient's name, dates, age, numbers, diagnosis or drugs.
Photo scene and mild difficulty: 轻度困难图。完整A4病历纸有很浅的十字折痕，摊开平整，纸中央仅有轻微明暗变化，文字无缺损。正上方略偏右3度拍摄，冷白色诊室光，淡米色桌面。不得加印章、遮挡或模糊。
Output in upright LANDSCAPE around 2048x1536 or greater. Fit all specified text on one full sheet using realistic black Chinese Song/Ming print of roughly the same size as reference. All page edges visible, enough margin so perspective never crops corners. Natural paper lighting and texture, text fully readable; no severe wrinkles/blur. Put unobtrusive small footer-corner "虚构测试样例 03 · 非真实就诊记录". NO new disclaimer heading, NO red stamp, NO logo, NO watermark across the body. This is a fictional test record, with printed simulated doctor's name, never imitate a real signature.
Exact complete text, do not paraphrase or omit, preserve diagnostic question marks and distinctions between negative/unknown/not performed:
北京中医药大学东直门医院国际部门诊病历
就诊时间：2026-10-10 10:42:08    就诊科室：国际部脾胃病科一区门诊
姓名：测试小蘑菇    性别：女    年龄：66岁    门诊号：TEST-20261010-003
主诉：胃镜病理提示肠化生后复诊，伴上腹不适2年。
现病史：间歇上腹隐痛及早饱，与饮食有一定关系。近1月症状较前减轻，无黑便及明显消瘦。携2026-09-12胃镜及病理报告复诊，希望核对病理部位与历次变化。
胃镜所见：胃窦黏膜红白相间，局部血管纹理可见；胃体未见明显糜烂。 病理部位：胃窦小弯、胃窦大弯、胃角。 病理诊断：胃窦小弯慢性萎缩性胃炎，轻度肠上皮化生；胃角慢性炎症；未见异型增生。 肠上皮化生：胃窦小弯轻度；其他部位按原报告核对。 幽门螺杆菌：本次病理染色阴性；既往根除治疗史不详。
既往史：高血压8年，口服氨氯地平5mg，每日1次；胆囊切除术后6年。 个人史：不吸烟、不饮酒，过去常食腌制食品；退休后作息较规律。 过敏史：头孢类药物用后皮疹，具体品种不详。 家族史：父亲70岁时诊断胃癌。
中医四诊：舌淡红，苔薄，脉细。
生命体征：血压138/82mmHg，脉搏72次/分；腹软，剑突下轻压痛。
西医诊断：慢性萎缩性胃炎伴肠上皮化生。
中医诊断：胃痞病：气阴不足证（模拟记录）。
药品处方：瑞巴派特片100mg，口服，每日3次，共14天；继续既往降压治疗，本次未调整。
中药配方：P太子参15g　P茯苓12g　P炒白术12g　P麦冬9g
P白芍12g　P陈皮6g　P炙甘草3g
中药7付，每天一剂，水煎服，分2次口服。
建议：保留本次病理原件，对照既往报告核对取材部位；复查计划由接诊医生结合完整资料确认。
（以下空白）
第1页/共1页    门诊医生：模拟医生丙
虚构测试样例 03 · 非真实就诊记录
Constraints: patient name exactly "测试小蘑菇". Exactly one photographed page, no collage or extra panels. Do not reuse reference case's content. No hands, paperweights, pens, covering objects, tears, damage, stains obscuring text, missing areas or illegible handwriting.

## 04_curl_bowel_symptoms

Use case: photorealistic-natural
Asset: one horizontal outpatient medical chart photo for OCR software testing.
Input image 1 is a FICTIONAL LAYOUT REFERENCE ONLY. Keep its EXACT hospital document template, landscape A4 orientation, title typography and placement, the two demographic rows between thin horizontal rules, narrow left section-label column, matching tab stops, multi-column herb prescription, lower blank area, （以下空白）, page count and physician footer. Title verbatim "北京中医药大学东直门医院国际部门诊病历". Department verbatim "国际部脾胃病科一区门诊". All left fixed labels in same order as reference: 主诉、现病史、既往史、中医四诊、生命体征、西医诊断、中医诊断、药品处方、中药配方、建议. Extra history and test information wraps in the existing right-hand content area, not new large section boxes.
Replace EVERY patient/clinical item from input with the exact new fictional case below; do not retain the reference patient's name, dates, age, numbers, diagnosis or drugs.
Photo scene and mild difficulty: 轻度困难图。整张A4纸边缘有轻微自然卷曲，右上角稍翘但不覆盖任何文字；纸张逆时针斜放约7度，柔和暖光下左下缘淡阴影，正文对比度正常清晰。浅灰桌面。
Output in upright LANDSCAPE around 2048x1536 or greater. Fit all specified text on one full sheet using realistic black Chinese Song/Ming print of roughly the same size as reference. All page edges visible, enough margin so perspective never crops corners. Natural paper lighting and texture, text fully readable; no severe wrinkles/blur. Put unobtrusive small footer-corner "虚构测试样例 04 · 非真实就诊记录". NO new disclaimer heading, NO red stamp, NO logo, NO watermark across the body. This is a fictional test record, with printed simulated doctor's name, never imitate a real signature.
Exact complete text, do not paraphrase or omit, preserve diagnostic question marks and distinctions between negative/unknown/not performed:
北京中医药大学东直门医院国际部门诊病历
就诊时间：2026-10-15 15:27:39    就诊科室：国际部脾胃病科一区门诊
姓名：假人小海带    性别：男    年龄：29岁    门诊号：TEST-20261015-004
主诉：腹痛伴大便次数增多8个月。
现病史：每周约3天脐周隐痛，排便后可缓解。大便每日2至4次，呈糊状，紧张、熬夜后加重。偶有黏液，无肉眼血便、夜间腹泻及发热。近半年体重稳定。
检查所见：2026-08-22结肠镜未见明显器质性病变；2026-10-08血红蛋白145g/L，C反应蛋白2.1mg/L，大便隐血阴性。 既往用药：曾自行服蒙脱石散，症状短暂缓解，剂量及次数不详。
既往史：无明确慢性病史；1年前有急性胃肠炎病史。否认肠道手术史。 个人史：久坐，工作压力较大，常饮咖啡；不吸烟，偶饮酒。 过敏史：无已知药物过敏；饮牛奶后易腹胀。 家族史：否认已知炎症性肠病家族史；其他家族史未提供。
中医四诊：舌淡红，苔薄白，脉弦。
生命体征：血压118/72mmHg，脉搏78次/分；腹软，左下腹轻压痛，无反跳痛。
西医诊断：肠易激综合征？（腹泻型，待结合完整检查确认）；功能性肠病待评估。
中医诊断：泄泻病：肝郁脾虚证（模拟记录）。
药品处方：本次未开具西药。
中药配方：P炒白术12g　P白芍12g　P防风6g　P陈皮6g
P山药15g　P茯苓12g　P炙甘草3g
中药7付，每天一剂，水煎服，分2次口服。
建议：记录排便频次、便形及诱发食物；补充既往肠镜原件，2周后复诊。
（以下空白）
第1页/共1页    门诊医生：模拟医生丁
虚构测试样例 04 · 非真实就诊记录
Constraints: patient name exactly "假人小海带". Exactly one photographed page, no collage or extra panels. Do not reuse reference case's content. No hands, paperweights, pens, covering objects, tears, damage, stains obscuring text, missing areas or illegible handwriting.

## 05_horizontal_fold_hp_followup

Use case: photorealistic-natural
Asset: one horizontal outpatient medical chart photo for OCR software testing.
Input image 1 is a FICTIONAL LAYOUT REFERENCE ONLY. Keep its EXACT hospital document template, landscape A4 orientation, title typography and placement, the two demographic rows between thin horizontal rules, narrow left section-label column, matching tab stops, multi-column herb prescription, lower blank area, （以下空白）, page count and physician footer. Title verbatim "北京中医药大学东直门医院国际部门诊病历". Department verbatim "国际部脾胃病科一区门诊". All left fixed labels in same order as reference: 主诉、现病史、既往史、中医四诊、生命体征、西医诊断、中医诊断、药品处方、中药配方、建议. Extra history and test information wraps in the existing right-hand content area, not new large section boxes.
Replace EVERY patient/clinical item from input with the exact new fictional case below; do not retain the reference patient's name, dates, age, numbers, diagnosis or drugs.
Photo scene and mild difficulty: 轻度困难图。完整A4纸有两条很浅的横向折痕，展开后仍可见细微纸纹。上半页柔和日光、下半页略偏暖但不变暗，整体斜拍约4度。所有边界与全文完整，字迹清晰，无强反光，不添加手或物品。
Output in upright LANDSCAPE around 2048x1536 or greater. Fit all specified text on one full sheet using realistic black Chinese Song/Ming print of roughly the same size as reference. All page edges visible, enough margin so perspective never crops corners. Natural paper lighting and texture, text fully readable; no severe wrinkles/blur. Put unobtrusive small footer-corner "虚构测试样例 05 · 非真实就诊记录". NO new disclaimer heading, NO red stamp, NO logo, NO watermark across the body. This is a fictional test record, with printed simulated doctor's name, never imitate a real signature.
Exact complete text, do not paraphrase or omit, preserve diagnostic question marks and distinctions between negative/unknown/not performed:
北京中医药大学东直门医院国际部门诊病历
就诊时间：2026-10-19 11:09:45    就诊科室：国际部脾胃病科一区门诊
姓名：测试小面包    性别：女    年龄：58岁    门诊号：TEST-20261019-005
主诉：幽门螺杆菌治疗后复诊，偶有上腹胀2周。
现病史：2026-08-30呼气试验阳性，外院予含铋四联方案14天，自述已完成。药名及剂量未带齐，治疗期间短暂恶心，停药后缓解。现偶有餐后腹胀，无持续腹痛、呕血或黑便。本次尚未复查呼气试验。
胃镜所见：2026-08-28胃窦黏膜轻度充血，未见溃疡。 病理诊断：慢性胃炎；未提供萎缩、肠化生的完整描述。 肠上皮化生：未知，待补原始病理报告。 幽门螺杆菌：治疗前阳性；治疗后尚未复查，不判定已根除。
既往史：2型糖尿病5年，口服二甲双胍500mg，每日2次；脂肪肝3年。否认消化性溃疡出血史。 个人史：不吸烟、不饮酒；三餐较规律，近期运动量减少。 过敏史：磺胺类药物过敏；青霉素过敏史未核实。 家族史：姐姐曾感染幽门螺杆菌；胃癌家族史未提供。
中医四诊：舌淡红，苔薄腻，脉滑。
生命体征：血压128/80mmHg，脉搏80次/分；腹软，无明显压痛。
西医诊断：幽门螺杆菌感染治疗后，根除结果待确认；慢性胃炎。
中医诊断：胃痞病：证候待确认。
药品处方：本次未重复开具抗菌药；原有糖尿病治疗继续，具体调整由原接诊医生确认。
中药配方：本次未开具中药处方；既往中药使用情况待核对。
建议：补充外院处方和完整病理原件；核对近期抑酸药使用情况，由接诊医生确定复查安排。
（以下空白）
第1页/共1页    门诊医生：模拟医生戊
虚构测试样例 05 · 非真实就诊记录
Constraints: patient name exactly "测试小面包". Exactly one photographed page, no collage or extra panels. Do not reuse reference case's content. No hands, paperweights, pens, covering objects, tears, damage, stains obscuring text, missing areas or illegible handwriting.