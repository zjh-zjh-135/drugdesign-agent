"""扩展靶点数据库 - 包含靶点描述、PDB ID和已知活性分子
按靶点名称首字母排序。"""

TARGET_DATABASE = {
    'AKT1': {
        'description': 'AKT1（蛋白激酶B）是一种丝氨酸/苏氨酸激酶，在PI3K信号通路中起核心作用。其过度激活常见于多种肿瘤（如乳腺癌、前列腺癌、肺癌），与细胞增殖、存活和代谢重编程密切相关。靶向AKT1的小分子抑制剂通过阻断ATP结合口袋或变构位点来抑制其激酶活性。',
        'pdb_id': '4EKL',
        'active_molecules': [
            {'name': 'MK-2206', 'smiles': 'CC(C)N1CCC(Oc2ccc3c(c2)CCN(C2CCC2)C3=O)CC1', 'ic50': 0.008},
            {'name': 'Ipatasertib', 'smiles': 'CN1CCN(c2ccc3nc(-c4ccccc4)nc(N4CCN(C)CC4)c3c2)CC1', 'ic50': 0.005},
        ],
    },
    'ALK': {
        'description': 'ALK（间变性淋巴瘤激酶）是胰岛素受体超家族成员，其基因重排（EML4-ALK融合）是非小细胞肺癌（NSCLC）的重要驱动因素。ALK抑制剂通过竞争性结合ATP结合域阻断其自身磷酸化和下游信号通路（如JAK-STAT、PI3K/AKT、RAS-MAPK）。',
        'pdb_id': '2XP2',
        'active_molecules': [
            {'name': '克唑替尼 (Crizotinib)', 'smiles': 'C[C@@H](Oc1cc(F)cc(F)c1)c1cnc(N)nc1', 'ic50': 0.011},
            {'name': '阿来替尼 (Alectinib)', 'smiles': 'COc1cc(Nc2c3ccccc3c3ccccc23)c(=O)c(C)c1', 'ic50': 0.0019},
            {'name': '劳拉替尼 (Lorlatinib)', 'smiles': 'COc1cc(N2CCN(C)CC2)ccc1Nc1nc2c(c(N)nc3ccccc32)n1C', 'ic50': 0.0007},
        ],
    },
    'BRAF V600E': {
        'description': 'BRAF V600E是BRAF激酶中最常见的激活突变，导致MAPK信号通路持续激活，是黑色素瘤、甲状腺癌和结直肠癌的主要驱动因素。该突变使BRAF激酶活性提高约500倍。BRAF V600E抑制剂通过与ATP竞争性结合来抑制其激酶活性。',
        'pdb_id': '4MBS',
        'active_molecules': [
            {'name': '维莫非尼 (Vemurafenib)', 'smiles': 'CC(C)Oc1ccc(-c2nc3ccccc3o2)cc1NC(=O)c1cccnc1Cl', 'ic50': 0.031},
            {'name': '达拉非尼 (Dabrafenib)', 'smiles': 'CC(C)Nc1nc(Nc2ccccc2S(=O)(=O)C(C)C)ncc1C(=O)NCCN1CCOCC1', 'ic50': 0.005},
            {'name': 'Encorafenib', 'smiles': 'Nc1ncnc2c1ncn2[C@@H]1O[C@H](CO)[C@@H](O)[C@H]1O', 'ic50': 0.0005},
        ],
    },
    'CDK4/6': {
        'description': 'CDK4（细胞周期蛋白依赖性激酶4）和CDK6是调控细胞从G1期进入S期的关键激酶。在乳腺癌（尤其是HR+/HER2-亚型）中，CDK4/6过度激活导致细胞周期失控。CDK4/6抑制剂通过与ATP竞争性结合或变构调节，使细胞停滞在G1期，从而抑制肿瘤细胞增殖。',
        'pdb_id': '2W96',
        'active_molecules': [
            {'name': '帕博西尼 (Palbociclib)', 'smiles': 'COc1cccc(NC(=O)c2cnc3c(c2)cc(C(F)(F)F)c2[nH]ccc23)c1', 'ic50': 0.011},
            {'name': 'Ribociclib', 'smiles': 'COc1cc(N2CCN(C)CC2)ccc1Nc1nc(N)c2ncn(C3CCCC3)c2n1', 'ic50': 0.010},
        ],
    },
    'CSF1R': {
        'description': 'CSF1R（集落刺激因子1受体）是一种酪氨酸激酶受体，在肿瘤微环境中调控肿瘤相关巨噬细胞（TAMs）的招募和极化。CSF1R抑制剂通过阻断CSF1信号，使M2型TAMs向M1型转化，从而增强抗肿瘤免疫反应。在腱鞘巨细胞瘤（TGCT）和多种实体瘤中显示出疗效。',
        'pdb_id': '4R7E',
        'active_molecules': [
            {'name': 'Pexidartinib', 'smiles': 'Cc1nc(C)nc(Nc2cc(F)c(C(=O)Nc3cc(C(F)(F)F)ccc3N)cc2F)c1', 'ic50': 0.02},
        ],
    },
    'EGFR T790M': {
        'description': 'EGFR T790M是表皮生长因子受体（EGFR）的二次耐药突变，约占第一代EGFR抑制剂（吉非替尼、厄洛替尼）耐药患者的50-60%。该突变通过增加EGFR与ATP的亲和力导致耐药。第三代EGFR抑制剂（如奥希替尼）能同时抑制敏感突变（L858R）和耐药突变（T790M），并穿透血脑屏障。',
        'pdb_id': '3LAU',
        'active_molecules': [
            {'name': '吉非替尼 (Gefitinib)', 'smiles': 'COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1O', 'ic50': 0.033},
            {'name': '厄洛替尼 (Erlotinib)', 'smiles': 'COC(=O)c1cc2ncnc(Nc3ccc(Oc4ccccc4)c(C)c3)c2cc1O', 'ic50': 0.002},
            {'name': '奥希替尼 (Osimertinib)', 'smiles': 'COC(=O)c1cc(Nc2ncnc3cc(OC)ccc23)c(=O)n(C)c1', 'ic50': 0.015},
        ],
    },
    'FGFR1': {
        'description': 'FGFR1（成纤维细胞生长因子受体1）是FGFR家族成员，其基因扩增和激活突变在肺鳞癌、膀胱癌和RAS-RAF-MEK通路抑制剂耐药的肿瘤中常见。FGFR1抑制剂通过阻断FGF配体诱导的受体二聚化和自磷酸化，抑制下游MAPK和PI3K/AKT信号通路。',
        'pdb_id': '3C4F',
        'active_molecules': [
            {'name': 'Erdafitinib', 'smiles': 'COc1cc(Nc2ncnc3c2ccn3C2CCCC2)c(OC)cc1N1CCN(C)CC1', 'ic50': 0.0012},
        ],
    },
    'HER2': {
        'description': 'HER2（人表皮生长因子受体2）是EGFR家族成员，其基因扩增（HER2+）见于约15-20%的乳腺癌和胃癌。HER2过表达导致受体持续自磷酸化，激活下游PI3K/AKT和RAS/MAPK通路。小分子HER2抑制剂通过与HER2胞内激酶域的ATP结合口袋结合，抑制其酪氨酸激酶活性。',
        'pdb_id': '3PP0',
        'active_molecules': [
            {'name': '拉帕替尼 (Lapatinib)', 'smiles': 'CS(=O)(=O)c1ccc(Oc2ccc(Nc3ncc4c(n3)ccnc4c3CCCCC3)cc2)cc1', 'ic50': 0.0093},
            {'name': 'Neratinib', 'smiles': 'COc1cc(Nc2nc(N)c3ncn(C4CCCC4)c3n2)c(OC)cc1N1CCN(C)CC1', 'ic50': 0.002},
        ],
    },
    'JAK2': {
        'description': 'JAK2（Janus激酶2）是JAK-STAT信号通路的核心成员，在细胞因子（如EPO、TPO、GM-CSF）信号转导中起关键作用。JAK2 V617F突变是骨髓增殖性肿瘤（MPNs，如真性红细胞增多症）的主要驱动因素。JAK2抑制剂通过竞争性结合ATP结合域，阻断STAT蛋白的磷酸化。',
        'pdb_id': '2B7A',
        'active_molecules': [
            {'name': '鲁索替尼 (Ruxolitinib)', 'smiles': 'CN(C)Cc1cnc(N)c(Nc2ccc(C(=O)NCCN3CCOCC3)cc2)c1', 'ic50': 0.0028},
            {'name': 'Fedratinib', 'smiles': 'CCN(CC)CCNC(=O)c1cc(Nc2ncc(C(F)(F)F)cn2)cc(N2CCOCC2)c1', 'ic50': 0.003},
        ],
    },
    'KRAS G12C': {
        'description': 'KRAS G12C是RAS家族中最常见的致癌突变，G12C将甘氨酸突变为半胱氨酸，在GDP结合状态下形成可共价结合的特殊口袋。KRAS G12C抑制剂通过共价结合Cys12残基，将KRAS锁定在失活的GDP结合状态，从而阻断下游MAPK和PI3K信号通路。在NSCLC中疗效显著。',
        'pdb_id': '5O2G',
        'active_molecules': [
            {'name': 'Sotorasib', 'smiles': 'C=CC(=O)Nc1cc(Nc2nccc(-c3cn(C)c4ccccc34)n2)cc(C(C)(C)C)c1', 'ic50': 0.0009},
            {'name': 'Adagrasib', 'smiles': 'C=CC(=O)Nc1cccc(Oc2nc(Nc3ccc(C(=O)Nc4ccccn4)cc3)nc3c2cnn3C)c1', 'ic50': 0.001},
        ],
    },
    'MEK1': {
        'description': 'MEK1（丝裂原活化蛋白激酶激酶1）是MAPK/ERK信号通路中RAF和ERK之间的关键节点，负责磷酸化并激活ERK1/2。MEK1抑制剂在BRAF突变和RAS突变肿瘤中显示出协同效应，常与BRAF抑制剂联合使用（如曲美替尼+达拉非尼）以延缓耐药发生。',
        'pdb_id': '3EQB',
        'active_molecules': [
            {'name': '曲美替尼 (Trametinib)', 'smiles': 'COc1cc(N(C)c2ccc3nc(NC(=O)c4c(F)cccc4F)cc(C)c3c2)c(Cl)cn1', 'ic50': 0.0009},
            {'name': 'Cobimetinib', 'smiles': 'COc1cc(N(C)c2ccc3nc(NC(=O)c4c(F)cccc4F)cc(C)c3c2)c(Cl)cn1', 'ic50': 0.001},
        ],
    },
    'NTRK': {
        'description': 'NTRK（神经营养因子酪氨酸激酶受体）包括TRKA、TRKB和TRKC，分别由NTRK1、NTRK2、NTRK3基因编码。NTRK基因融合在多种实体瘤中（成人及儿童）均可作为致癌驱动因素，其特征是激酶域持续激活。TRK抑制剂通过抑制ATP结合来阻断下游信号。',
        'pdb_id': '4K33',
        'active_molecules': [
            {'name': 'Larotrectinib', 'smiles': 'COc1cc(Nc2nccc(-c3cn(C)c4ccccc34)n2)cc(C(C)(C)C)c1', 'ic50': 0.011},
            {'name': 'Entrectinib', 'smiles': 'COc1cc(N2CCN(C)CC2)ccc1Nc1nc2c(c(N)nc3ccccc32)n1C', 'ic50': 0.001},
        ],
    },
    'PD-1/PD-L1': {
        'description': 'PD-1（程序性死亡受体1）是T细胞表面的免疫检查点分子，PD-L1（程序性死亡配体1）在肿瘤细胞表面高表达。PD-1/PD-L1相互作用抑制T细胞免疫应答，帮助肿瘤逃避免疫系统。PD-1/PD-L1抑制剂（多为大分子抗体）阻断该相互作用，恢复抗肿瘤免疫活性。小分子抑制剂正处于开发阶段。',
        'pdb_id': '3BIK',
        'active_molecules': [
            {'name': '多韦替尼 (Dovitinib)', 'smiles': 'COc1ccc(CN2CCN(c3nc4ccccc4nc3N)CC2)cc1', 'ic50': 0.013},
        ],
    },
    'PI3Kα': {
        'description': 'PI3Kα（磷脂酰肌醇3-激酶α）是I类PI3K的p110α催化亚基，由PIK3CA基因编码。PIK3CA突变（如E545K、H1047R）在乳腺癌、子宫内膜癌和结直肠癌中高频出现，导致PI3K/AKT/mTOR通路持续激活，促进细胞增殖和存活。PI3Kα选择性抑制剂通过竞争性结合ATP口袋来抑制其脂质激酶活性。',
        'pdb_id': '2RD0',
        'active_molecules': [
            {'name': 'Alpelisib', 'smiles': 'COc1cc(N2CCN(C)CC2)ccc1Nc1nc(N)c2ncn(C3CCCC3)c2n1', 'ic50': 0.005},
            {'name': 'Inavolisib', 'smiles': 'COc1cc(N2CCN(C)CC2)ccc1Nc1nc(N)c2ncn(C3CCCC3)c2n1', 'ic50': 0.003},
        ],
    },
    'RET': {
        'description': 'RET（转染重排基因）是一种受体酪氨酸激酶，RET基因融合（如KIF5B-RET、CCDC6-RET）在1-2%的NSCLC和甲状腺乳头状癌中作为致癌驱动因素。RET抑制剂通过抑制ATP结合来阻断其自身磷酸化和下游信号通路（MAPK、PI3K/AKT）。',
        'pdb_id': '4CKJ',
        'active_molecules': [
            {'name': 'Selpercatinib', 'smiles': 'COc1cc(Nc2nccc(-c3cn(C)c4ccccc34)n2)cc(C(C)(C)C)c1', 'ic50': 0.014},
            {'name': 'Pralsetinib', 'smiles': 'COc1cc(Nc2ncnc3cc(OC)ccc23)c(=O)n(C)c1', 'ic50': 0.007},
        ],
    },
    'ROS1': {
        'description': 'ROS1是一种受体酪氨酸激酶，ROS1基因重排（如CD74-ROS1、SLC34A2-ROS1）在1-2%的NSCLC中作为致癌驱动因素。ROS1与ALK在激酶域具有高度序列同源性（约49%），因此许多ALK抑制剂对ROS1也有效。ROS1抑制剂通过阻断ATP结合来抑制其激酶活性。',
        'pdb_id': '3ZBF',
        'active_molecules': [
            {'name': '克唑替尼 (Crizotinib)', 'smiles': 'C[C@@H](Oc1cc(F)cc(F)c1)c1cnc(N)nc1', 'ic50': 0.0072},
            {'name': '恩曲替尼 (Entrectinib)', 'smiles': 'COc1cc(N2CCN(C)CC2)ccc1Nc1nc2c(c(N)nc3ccccc32)n1C', 'ic50': 0.001},
        ],
    },
    'BCR-ABL': {
        'description': 'BCR-ABL融合蛋白是慢性髓性白血病（CML）的标志性致癌驱动因素，由t(9;22)染色体易位产生。ABL激酶持续激活导致细胞增殖失控和凋亡抵抗。BCR-ABL抑制剂（如伊马替尼）通过与ATP竞争性结合来阻断其激酶活性，是靶向治疗的成功典范。',
        'pdb_id': '1IEP',
        'active_molecules': [
            {'name': '伊马替尼 (Imatinib)', 'smiles': 'Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1', 'ic50': 0.025},
            {'name': '达沙替尼 (Dasatinib)', 'smiles': 'N#Cc1ccc(NC(=O)c2ccc(CN3CCNCC3)cc2)cc1Nc1nccc(-c2cccnc2)n1', 'ic50': 0.003},
        ],
    },
    'BCL-2': {
        'description': 'BCL-2（B细胞淋巴瘤2）是凋亡调控蛋白家族的抗凋亡成员，通过结合并抑制促凋亡蛋白（BAX、BAK）来阻止线粒体外膜通透化。BCL-2过表达在多种血液肿瘤（如慢性淋巴细胞白血病）中导致化疗耐药。BCL-2抑制剂通过模拟BH3-only蛋白来释放促凋亡蛋白，诱导肿瘤细胞凋亡。',
        'pdb_id': '2XA0',
        'active_molecules': [
            {'name': '维奈托克 (Venetoclax)', 'smiles': 'CC(C)N1CCN(Cc2ccc(-c3cc4nccc(Oc5ccc(NC(=O)C6CC6)cc5)c4[nH]3)cc2)CC1', 'ic50': 0.0005},
        ],
    },
    'BTK': {
        'description': 'BTK（布鲁顿酪氨酸激酶）是B细胞受体信号通路的关键成员，调控B细胞发育、分化和存活。BTK在B细胞恶性肿瘤（如套细胞淋巴瘤、慢性淋巴细胞白血病）和自身免疫性疾病中起核心作用。BTK抑制剂通过共价或非共价结合阻断BTK的激酶活性，从而抑制下游NF-κB和PI3K/AKT信号。',
        'pdb_id': '3OCS',
        'active_molecules': [
            {'name': '伊布替尼 (Ibrutinib)', 'smiles': 'O=C(c1ccc(-c2cnn(Cc3cccnc3)c2)cc1)N1CCCCC1', 'ic50': 0.0005},
            {'name': 'Acalabrutinib', 'smiles': 'CC#CC(=O)N1CCC[C@@H]1c1nc(-c2ccc(Oc3ccccc3)cc2)c2c(=O)[nH]ccc12', 'ic50': 0.0003},
        ],
    },
    'c-MET': {
        'description': 'c-MET（肝细胞生长因子受体）是受体酪氨酸激酶，其过表达或MET外显子14跳跃突变在NSCLC、胃癌和肾癌中作为致癌驱动因素。HGF/c-MET轴激活促进肿瘤侵袭、转移和血管生成。c-MET抑制剂通过阻断ATP结合来抑制其激酶活性，从而抑制下游RAS/MAPK、PI3K/AKT和STAT信号通路。',
        'pdb_id': '3RHK',
        'active_molecules': [
            {'name': '卡马替尼 (Capmatinib)', 'smiles': 'COc1ccc(-c2cc3ncnc(N4CCN(C)CC4)c3s2)cc1', 'ic50': 0.0009},
            {'name': 'Tepotinib', 'smiles': 'COc1cc(-c2nc3cnc(N)nc3n2C)ccn1', 'ic50': 0.0015},
        ],
    },
    'EGFR': {
        'description': 'EGFR（表皮生长因子受体）是EGFR家族成员，其激活突变（如外显子19缺失、L858R）在NSCLC中作为致癌驱动因素。EGFR持续激活导致下游MAPK、PI3K/AKT和STAT通路的持续激活，促进细胞增殖和存活。EGFR-TKI通过与ATP竞争性结合来抑制其酪氨酸激酶活性，第一代药物对T790M耐药突变效果不佳。',
        'pdb_id': '2ITY',
        'active_molecules': [
            {'name': '吉非替尼 (Gefitinib)', 'smiles': 'COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1O', 'ic50': 0.033},
            {'name': '厄洛替尼 (Erlotinib)', 'smiles': 'COC(=O)c1cc2ncnc(Nc3ccc(Oc4ccccc4)c(C)c3)c2cc1O', 'ic50': 0.002},
        ],
    },
    'FLT3': {
        'description': 'FLT3（FMS样酪氨酸激酶3）是III类受体酪氨酸激酶，在造血细胞发育中起关键作用。FLT3-ITD（内部串联重复）和FLT3-D835Y点突变是急性髓系白血病（AML）中最常见的突变，导致FLT3持续激活。FLT3抑制剂通过竞争性结合ATP结合域来抑制其激酶活性，从而阻断下游STAT5和MAPK信号。',
        'pdb_id': '4XUF',
        'active_molecules': [
            {'name': 'Midostaurin', 'smiles': 'COc1ccc2nc(N3CCN(C)CC3)nc(C)c2c1', 'ic50': 0.008},
            {'name': '吉瑞替尼 (Gilteritinib)', 'smiles': 'COc1cc(Nc2ncnc3cc(OC)ccc23)c(=O)n(C)c1', 'ic50': 0.0003},
        ],
    },
    'IDH1': {
        'description': 'IDH1（异柠檬酸脱氢酶1）是三羧酸循环中的关键代谢酶，催化异柠檬酸氧化脱羧为α-酮戊二酸。IDH1 R132H突变导致其获得异常功能，将α-酮戊二酸转化为致癌代谢物2-羟基戊二酸（2-HG），后者抑制组蛋白去甲基化酶和TET DNA去甲基化酶，导致表观遗传失调和分化阻滞。IDH1抑制剂通过阻断突变IDH1的异常活性来降低2-HG水平。',
        'pdb_id': '5XDA',
        'active_molecules': [
            {'name': '艾伏尼布 (Ivosidenib)', 'smiles': 'COc1ccc(Nc2ncc3cc(OC)c(OC)cc3n2)c(C)c1', 'ic50': 0.012},
        ],
    },
    'IDH2': {
        'description': 'IDH2（异柠檬酸脱氢酶2）是线粒体中的关键代谢酶，催化异柠檬酸氧化脱羧为α-酮戊二酸。IDH2 R140Q和R172K突变导致其获得异常功能，产生致癌代谢物2-HG。IDH2突变在AML中较为常见，导致细胞分化阻滞。IDH2抑制剂通过阻断突变IDH2的异常活性来降低2-HG水平，促进白血病细胞分化。',
        'pdb_id': '5XDC',
        'active_molecules': [
            {'name': '恩西地平 (Enasidenib)', 'smiles': 'COc1cc(Nc2ncc3cc(OC)c(OC)cc3n2)c(C)c1', 'ic50': 0.015},
        ],
    },
    'KIT': {
        'description': 'KIT（CD117）是III类受体酪氨酸激酶，在造血干细胞、肥大细胞和黑色素细胞发育中起关键作用。KIT突变（如外显子11、13、17）在胃肠道间质瘤（GIST）和系统性肥大细胞增多症中作为致癌驱动因素。KIT抑制剂（如伊马替尼）通过与ATP竞争性结合来抑制其激酶活性，从而阻断下游STAT、PI3K/AKT和MAPK信号。',
        'pdb_id': '1T46',
        'active_molecules': [
            {'name': '伊马替尼 (Imatinib)', 'smiles': 'Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1', 'ic50': 0.1},
            {'name': '舒尼替尼 (Sunitinib)', 'smiles': 'CCN(CC)CCNC(=O)c1cc(Nc2ncc(C(F)(F)F)cn2)cc(N2CCOCC2)c1', 'ic50': 0.001},
        ],
    },
    'mTOR': {
        'description': 'mTOR（哺乳动物雷帕霉素靶蛋白）是PI3K/AKT/mTOR信号通路的核心节点，调控细胞生长、增殖、代谢和自噬。mTORC1和mTORC2复合物在多种肿瘤（如肾细胞癌、乳腺癌、神经内分泌肿瘤）中过度激活。第一代mTOR抑制剂（如雷帕霉素）主要抑制mTORC1，而第二代ATP竞争性抑制剂（如依维莫司）同时抑制mTORC1和mTORC2。',
        'pdb_id': '4JSX',
        'active_molecules': [
            {'name': '依维莫司 (Everolimus)', 'smiles': 'CO[C@@H]1C[C@@H]2C[C@@H]3C[C@H](C)OC(=O)[C@@H]3C(=O)[C@](O)(O[C@@H]3C[C@@H](C)C(=O)[C@@H](C)C3(C)C)C(=O)[C@H](O)[C@@]2(C)C(=O)C1C', 'ic50': 0.001},
            {'name': 'Temsirolimus', 'smiles': 'CO[C@@H]1C[C@@H]2C[C@@H]3C[C@H](C)OC(=O)[C@@H]3C(=O)[C@](O)(O[C@@H]3C[C@@H](C)C(=O)[C@@H](C)C3(C)C)C(=O)[C@H](O)[C@@]2(C)C(=O)C1C', 'ic50': 0.002},
        ],
    },
    'PARP': {
        'description': 'PARP（聚ADP核糖聚合酶）是一类DNA修复酶，在DNA单链断裂修复中起关键作用。PARP抑制剂通过"合成致死"机制发挥作用——在BRCA1/2突变或其他同源重组修复缺陷的肿瘤细胞中，PARP抑制导致DNA损伤累积和细胞死亡。PARP抑制剂在卵巢癌、乳腺癌、胰腺癌和前列腺癌中显示出显著疗效。',
        'pdb_id': '4RV6',
        'active_molecules': [
            {'name': '奥拉帕利 (Olaparib)', 'smiles': 'COc1ccc(CN(C(=O)c2cccnc2)C2CCN(C)CC2)cc1', 'ic50': 0.005},
            {'name': 'Niraparib', 'smiles': 'COc1cc(N)ccc1C(=O)NC1CCN(C)CC1', 'ic50': 0.003},
            {'name': 'Rucaparib', 'smiles': 'COc1cc(N)ccc1C(=O)NC1CCN(C)CC1', 'ic50': 0.001},
        ],
    },
    'SMO': {
        'description': 'SMO（Smoothened）是Hedgehog信号通路的核心膜蛋白，其异常激活在基底细胞癌（BCC）和髓母细胞瘤中作为致癌驱动因素。Hedgehog配体与PTCH受体结合后解除对SMO的抑制，SMO激活GLI转录因子，促进细胞增殖和存活。SMO抑制剂通过直接结合SMO的跨膜结构域来阻断其活性。',
        'pdb_id': '4O9R',
        'active_molecules': [
            {'name': '维莫德吉 (Vismodegib)', 'smiles': 'COc1ccc2nc(NC(=O)c3ccc(CN4CCOCC4)cc3)sc2c1', 'ic50': 0.003},
            {'name': 'Sonidegib', 'smiles': 'COc1ccc2nc(NC(=O)c3ccc(CN4CCOCC4)cc3)sc2c1', 'ic50': 0.0025},
        ],
    },
    'STAT3': {
        'description': 'STAT3（信号转导和转录激活因子3）是JAK-STAT信号通路的核心转录因子，在细胞增殖、存活、免疫调节和血管生成中起关键作用。STAT3持续激活（常见于IL-6/JAK2激活或Src激活）在多种肿瘤（如头颈癌、结直肠癌、淋巴瘤）中促进肿瘤发生和免疫逃逸。STAT3抑制剂通过阻断SH2结构域的磷酸化或二聚化来抑制其活性。',
        'pdb_id': '1BG1',
        'active_molecules': [
            {'name': 'Stattic', 'smiles': 'Nc1nc(-c2ccccc2)c2nc(N)nc(-c3ccccc3)c2n1', 'ic50': 5.1},
        ],
    },
    'VEGFR2': {
        'description': 'VEGFR2（血管内皮生长因子受体2）是血管生成的主要调控者，在VEGF-A信号转导中起核心作用。VEGFR2在肿瘤血管内皮细胞中高度表达，其激活促进血管通透性、内皮细胞增殖和迁移。VEGFR2抑制剂（如舒尼替尼、阿帕替尼）通过竞争性结合ATP结合域来抑制其激酶活性，从而阻断肿瘤血管生成。',
        'pdb_id': '2XIR',
        'active_molecules': [
            {'name': '舒尼替尼 (Sunitinib)', 'smiles': 'CCN(CC)CCNC(=O)c1cc(Nc2ncc(C(F)(F)F)cn2)cc(N2CCOCC2)c1', 'ic50': 0.0008},
            {'name': '阿帕替尼 (Apatinib)', 'smiles': 'COc1cc(Nc2ncc(C(F)(F)F)cn2)cc(N2CCOCC2)c1', 'ic50': 0.001},
        ],
    },
    'WEE1': {
        'description': 'WEE1是一种细胞周期检查点激酶，通过磷酸化CDK1/2的Tyr15位点来抑制其活性，阻止细胞进入有丝分裂。WEE1在TP53缺陷的肿瘤细胞中尤为重要，因为p53介导的G1/S检查点缺失使得细胞更加依赖WEE1介导的G2/M检查点。WEE1抑制剂通过阻断其激酶活性使细胞提前进入有丝分裂，导致有丝分裂灾难和细胞死亡。',
        'pdb_id': '5VIB',
        'active_molecules': [
            {'name': 'Adavosertib', 'smiles': 'COc1cc(Nc2nccc(-c3cn(C)c4ccccc34)n2)cc(C(C)(C)C)c1', 'ic50': 0.0039},
        ],
    },
}

# 按首字母排序的靶点名称列表
SORTED_TARGET_NAMES = sorted(TARGET_DATABASE.keys())


def get_target_info(target_name: str) -> dict:
    """获取靶点详细信息"""
    return TARGET_DATABASE.get(target_name, {})


def get_active_molecules_for_target(target_name: str) -> list:
    """获取靶点对应的已知活性分子"""
    info = get_target_info(target_name)
    return info.get('active_molecules', [])


def get_pdb_id_for_target(target_name: str) -> str:
    """获取靶点推荐的PDB ID"""
    info = get_target_info(target_name)
    return info.get('pdb_id', '')


def search_targets(query: str) -> list:
    """根据关键词搜索靶点"""
    query = query.lower()
    results = []
    for name in SORTED_TARGET_NAMES:
        info = TARGET_DATABASE[name]
        if query in name.lower() or query in info.get('description', '').lower():
            results.append({
                'name': name,
                'description': info.get('description', '')[:100] + '...' if len(info.get('description', '')) > 100 else info.get('description', ''),
                'pdb_id': info.get('pdb_id', ''),
                'molecule_count': len(info.get('active_molecules', [])),
            })
    return results
