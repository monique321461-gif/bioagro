import re
import sqlite3
import bcrypt
import streamlit as st

st.set_page_config(page_title="Bioagro", page_icon="🌱", layout="centered")

# ---------- Idiomas: textos no formato "pt|en|es|zh" ----------
LANGS = {"Português": 0, "English": 1, "Español": 2, "中文": 3}
st.sidebar.selectbox("🌐", list(LANGS), key="langname")
LANG = LANGS[st.session_state.get("langname", "Português")]


def L(s):
    return s.split("|")[LANG]


# ---------- Banco de dados ----------
@st.cache_resource
def conn():
    c = sqlite3.connect("bioagro.db", check_same_thread=False)
    c.execute("create table if not exists users(email text primary key, name text, pw blob, role text)")
    c.execute("create table if not exists projects(id integer primary key autoincrement, email text, name text, mwh real, saving real, co2 real, payback text)")
    c.commit()
    return c


db = conn()

# ---------- Dados didáticos (estimativas, edite à vontade) ----------
# nome, kWh de energia por tonelada, custo de coleta (R$/t)
BIO = [
    ("Palha de milho|Corn stover|Paja de maíz|玉米秸秆", 778, 60),
    ("Palha de soja|Soy straw|Paja de soja|大豆秸秆", 778, 55),
    ("Bagaço de cana|Sugarcane bagasse|Bagazo de caña|甘蔗渣", 417, 15),
    ("Casca de arroz|Rice husk|Cascarilla de arroz|稻壳", 722, 30),
    ("Esterco bovino|Cattle manure|Estiércol bovino|牛粪", 60, 10),
]
# tecnologia, custo por kW instalado (R$)
TECH = {
    "gas": ("Gaseificação|Gasification|Gasificación|气化", 11000),
    "comb": ("Combustão com caldeira e turbina a vapor|Boiler and steam turbine combustion|Combustión con caldera y turbina de vapor|锅炉与蒸汽轮机燃烧", 9000),
    "bio": ("Biodigestão (biogás)|Biodigestion (biogas)|Biodigestión (biogás)|沼气发酵", 8000),
}
TECH_OF = ["gas", "gas", "comb", "comb", "bio"]
EQ = [
    ("Triturador|Shredder|Triturador|粉碎机", .08),
    ("Secador|Dryer|Secador|干燥机", .10),
    ("Esteira de alimentação|Feed conveyor|Cinta de alimentación|进料输送带", .07),
    (None, .30),
    ("Turbina ou gerador|Turbine or generator|Turbina o generador|涡轮机或发电机", .25),
    ("Filtro de gases|Gas filter|Filtro de gases|烟气过滤器", .08),
    ("Painel de controle e conexão à rede|Control panel and grid connection|Panel de control y conexión a la red|控制柜与并网", .12),
]
SUPPLIERS = [
    "Fornecedores de equipamentos|Equipment suppliers|Proveedores de equipos|设备供应商",
    "Engenharia e instalação|Engineering and installation|Ingeniería e instalación|工程与安装",
    "Licenciamento ambiental|Environmental licensing|Licenciamiento ambiental|环境许可",
    "Manutenção|Maintenance|Mantenimiento|维护",
]
CORE = {"gas": "Reator de gaseificação|Gasification reactor|Reactor de gasificación|气化反应器",
        "comb": "Caldeira|Boiler|Caldera|锅炉",
        "bio": "Biodigestor|Biodigester|Biodigestor|沼气池"}


def money(x):
    return "R$ {:,.0f}".format(x)


def calc(i, ton, tar):
    kwh = BIO[i][1] * ton
    kw = kwh / 7000
    inv = kw * TECH[TECH_OF[i]][1]
    om = inv * 0.08
    gross = kwh * tar
    net = gross - BIO[i][2] * ton - om
    return dict(i=i, ton=ton, tar=tar, kwh=kwh, kw=kw, inv=inv, om=om, gross=gross, net=net, co2=kwh / 1000 * 0.08)


def pmt(r, n, p):
    return p * r / (1 - (1 + r) ** -n)


def disclaimer():
    st.caption(L("Valores são estimativas didáticas. Este app não é consultoria financeira.|Values are educational estimates. This app is not financial advice.|Los valores son estimaciones didácticas. Esta app no es asesoría financiera.|数值仅为教学估算。本应用不构成财务建议。"))


# ---------- Cadastro e login ----------
def auth():
    st.title("🌱 Bioagro")
    st.caption(L("Do resíduo à energia, financiada por Fiagros|From waste to energy, funded by Fiagros|Del residuo a la energía, financiada por Fiagros|从废弃物到能源，由Fiagro提供资金"))
    t1, t2 = st.tabs([L("Entrar|Log in|Entrar|登录"), L("Cadastrar|Sign up|Registrarse|注册")])
    with t1:
        e = st.text_input("E-mail", key="le")
        p = st.text_input(L("Senha|Password|Contraseña|密码"), type="password", key="lp")
        if st.button(L("Entrar|Log in|Entrar|登录"), key="b1"):
            r = db.execute("select name,pw,role from users where email=?", (e.strip().lower(),)).fetchone()
            if r and bcrypt.checkpw(p.encode(), r[1]):
                st.session_state.user = {"email": e.strip().lower(), "name": r[0], "role": r[2]}
                st.rerun()
            else:
                st.error(L("E-mail ou senha incorretos.|Wrong e-mail or password.|Correo o contraseña incorrectos.|邮箱或密码错误。"))
    with t2:
        n = st.text_input(L("Nome|Name|Nombre|姓名"), key="sn")
        e = st.text_input("E-mail", key="se")
        p = st.text_input(L("Senha (mín. 8 caracteres)|Password (min. 8 characters)|Contraseña (mín. 8 caracteres)|密码（至少8个字符）"), type="password", key="sp")
        p2 = st.text_input(L("Confirmar senha|Confirm password|Confirmar contraseña|确认密码"), type="password", key="sp2")
        role = st.radio(L("Eu sou|I am|Soy|我是"), ["producer", "investor"], key="sr",
                        format_func=lambda x: L("Produtor rural|Farmer|Productor rural|农场主") if x == "producer" else L("Investidor|Investor|Inversor|投资者"))
        ok = st.checkbox(L("Aceito os Termos de Uso e a Política de Privacidade (LGPD)|I accept the Terms of Use and Privacy Policy (LGPD)|Acepto los Términos de Uso y la Política de Privacidad (LGPD)|我接受使用条款和隐私政策 (LGPD)"), key="sok")
        st.caption(L("Usamos seu nome e e-mail só para criar sua conta. A senha é guardada criptografada.|We use your name and e-mail only to create your account. Your password is stored encrypted.|Usamos tu nombre y correo solo para crear tu cuenta. La contraseña se guarda cifrada.|我们仅使用您的姓名和邮箱创建账户，密码经加密存储。"))
        if st.button(L("Criar conta|Create account|Crear cuenta|创建账户"), key="b2"):
            e = e.strip().lower()
            if not n.strip():
                st.error(L("Informe seu nome.|Enter your name.|Ingresa tu nombre.|请输入姓名。"))
            elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e):
                st.error(L("E-mail inválido.|Invalid e-mail.|Correo inválido.|邮箱无效。"))
            elif len(p) < 8:
                st.error(L("A senha precisa ter pelo menos 8 caracteres.|Password must have at least 8 characters.|La contraseña debe tener al menos 8 caracteres.|密码至少需要8个字符。"))
            elif p != p2:
                st.error(L("As senhas não são iguais.|Passwords do not match.|Las contraseñas no coinciden.|两次密码不一致。"))
            elif not ok:
                st.error(L("Aceite os termos para continuar.|Accept the terms to continue.|Acepta los términos para continuar.|请接受条款以继续。"))
            elif db.execute("select 1 from users where email=?", (e,)).fetchone():
                st.error(L("Este e-mail já está cadastrado.|This e-mail is already registered.|Este correo ya está registrado.|该邮箱已注册。"))
            else:
                db.execute("insert into users values(?,?,?,?)", (e, n.strip(), bcrypt.hashpw(p.encode(), bcrypt.gensalt()), role))
                db.commit()
                st.session_state.user = {"email": e, "name": n.strip(), "role": role}
                st.rerun()


# ---------- Páginas do produtor ----------
def page_bio():
    st.header(L("Qual biomassa rende mais?|Which biomass yields more?|¿Qué biomasa rinde más?|哪种生物质产能更高？"))
    tar0 = st.session_state.get("tar", 0.8)
    rows = []
    for i, (nm, kt, cost) in enumerate(BIO):
        rows.append({L("Biomassa|Biomass|Biomasa|生物质"): L(nm), "kWh/t": kt,
                     L("Custo coleta R$/t|Collection cost R$/t|Costo recolección R$/t|收集成本 R$/吨"): cost,
                     L("Ganho líquido R$/t|Net gain R$/t|Ganancia neta R$/t|净收益 R$/吨"): round(kt * tar0 - cost)})
    key = L("Ganho líquido R$/t|Net gain R$/t|Ganancia neta R$/t|净收益 R$/吨")
    rows.sort(key=lambda r: -r[key])
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.caption(L("Fórmula: kWh/t = poder calorífico × eficiência 20% ÷ 3,6. Fontes: EMBRAPA, Agrolink.|Formula: kWh/t = calorific value × 20% efficiency ÷ 3.6. Sources: EMBRAPA, Agrolink.|Fórmula: kWh/t = poder calorífico × eficiencia 20% ÷ 3,6. Fuentes: EMBRAPA, Agrolink.|公式：kWh/吨 = 热值 × 20%效率 ÷ 3.6。来源：EMBRAPA, Agrolink。"))
    st.subheader(L("Sua escolha|Your choice|Tu elección|您的选择"))
    i = st.selectbox(L("Biomassa que vou usar|Biomass I will use|Biomasa que usaré|我将使用的生物质"), range(len(BIO)), format_func=lambda x: L(BIO[x][0]))
    ton = st.number_input(L("Toneladas por ano|Tonnes per year|Toneladas por año|每年吨数"), 10, 100000, int(st.session_state.get("ton", 500)), 50)
    tar = st.number_input(L("Tarifa de energia (R$/kWh)|Energy tariff (R$/kWh)|Tarifa de energía (R$/kWh)|电价 (R$/kWh)"), 0.2, 2.0, float(tar0), 0.05)
    if st.button(L("Usar esta biomassa|Use this biomass|Usar esta biomasa|使用该生物质")):
        st.session_state.update(sel=i, ton=ton, tar=tar)
        st.success(L("Salvo! Vá para a próxima etapa no menu.|Saved! Go to the next step in the menu.|¡Guardado! Ve al siguiente paso en el menú.|已保存！请在菜单中进入下一步。"))


def cfg():
    if "sel" not in st.session_state:
        st.info(L("Primeiro escolha a biomassa na etapa 1.|First choose the biomass in step 1.|Primero elige la biomasa en el paso 1.|请先在第1步选择生物质。"))
        return None
    return calc(st.session_state.sel, st.session_state.ton, st.session_state.tar)


def page_tech():
    c = cfg()
    if not c:
        return
    t = TECH_OF[c["i"]]
    st.header(L("Tecnologia e equipamentos|Technology and equipment|Tecnología y equipos|技术与设备"))
    st.write(L("**Tecnologia recomendada:** |**Recommended technology:** |**Tecnología recomendada:** |**推荐技术：**") + L(TECH[t][0]))
    st.write("{:.0f} kW · {} · {}".format(c["kw"], L("Investimento estimado|Estimated investment|Inversión estimada|预计投资"), money(c["inv"])))
    rows = []
    for nm, f in EQ:
        rows.append({L("Equipamento|Equipment|Equipo|设备"): L(nm or CORE[t]), L("Custo estimado|Estimated cost|Costo estimado|预计成本"): money(c["inv"] * f)})
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.subheader(L("Quem contratar|Who to hire|A quién contratar|需要聘请谁"))
    for s in SUPPLIERS:
        st.write("• " + L(s))
    st.caption(L("São tipos de empresa, não parceiras. O orçamento real vem dos fornecedores.|These are company types, not partners. Real quotes come from suppliers.|Son tipos de empresa, no socios. El presupuesto real viene de los proveedores.|以上为公司类型，并非合作方。实际报价以供应商为准。"))


def page_viab():
    c = cfg()
    if not c:
        return
    st.header(L("Viabilidade|Feasibility|Viabilidad|可行性"))
    a, b = st.columns(2)
    a.metric(L("Energia por ano|Energy per year|Energía por año|年发电量"), "{:,.0f} MWh".format(c["kwh"] / 1000))
    b.metric(L("Economia líquida/ano|Net savings/year|Ahorro neto/año|年净节省"), money(c["net"]))
    a.metric(L("Investimento|Investment|Inversión|投资"), money(c["inv"]))
    b.metric(L("CO₂ evitado/ano|CO₂ avoided/year|CO₂ evitado/año|年减排CO₂"), "{:.1f} t".format(c["co2"]))
    pb = c["inv"] / c["net"] if c["net"] > 0 else None
    pbtxt = "{:.1f} {}".format(pb, L("anos|years|años|年")) if pb else "—"
    st.metric("Payback", pbtxt)
    st.bar_chart([-c["inv"] + c["net"] * y for y in range(1, 11)])
    st.caption(L("Saldo acumulado em 10 anos, sem financiamento. Fórmula: economia = kWh × tarifa − coleta − operação (8% do investimento/ano).|Cumulative balance over 10 years, no financing. Formula: savings = kWh × tariff − collection − operation (8% of investment/year).|Saldo acumulado en 10 años, sin financiación. Fórmula: ahorro = kWh × tarifa − recolección − operación (8% de la inversión/año).|10年累计余额（无融资）。公式：节省 = kWh × 电价 − 收集 − 运营（每年投资的8%）。"))
    name = st.text_input(L("Nome do projeto|Project name|Nombre del proyecto|项目名称"), "Projeto 1")
    if st.button(L("Salvar projeto|Save project|Guardar proyecto|保存项目")):
        u = st.session_state.user
        db.execute("insert into projects(email,name,mwh,saving,co2,payback) values(?,?,?,?,?,?)", (u["email"], name, c["kwh"] / 1000, c["net"], c["co2"], pbtxt))
        db.commit()
        st.success("✅")


def page_fiagro():
    c = cfg()
    if not c:
        return
    st.header(L("Financiamento via Fiagro|Financing via Fiagro|Financiación vía Fiagro|通过Fiagro融资"))
    tax = st.slider(L("Taxa do Fiagro (% a.a.)|Fiagro rate (% p.a.)|Tasa del Fiagro (% anual)|Fiagro利率（年%）"), 6.0, 20.0, 12.0, 0.5) / 100
    bank = st.slider(L("Taxa do banco (% a.a.)|Bank rate (% p.a.)|Tasa del banco (% anual)|银行利率（年%）"), 6.0, 30.0, 16.0, 0.5) / 100
    n = st.slider(L("Prazo (anos)|Term (years)|Plazo (años)|期限（年）"), 2, 10, 5)
    pf, pbk = pmt(tax, n, c["inv"]), pmt(bank, n, c["inv"])
    a, b = st.columns(2)
    a.metric("Fiagro", money(pf) + "/" + L("ano|year|año|年"))
    b.metric(L("Banco|Bank|Banco|银行"), money(pbk) + "/" + L("ano|year|año|年"))
    st.write(L("Economia total escolhendo o Fiagro: |Total savings choosing Fiagro: |Ahorro total eligiendo Fiagro: |选择Fiagro的总节省：") + money(pbk * n - pf * n))
    bf, bb, cum, s = c["inv"], c["inv"], [], 0
    sf, sb = [], []
    for y in range(1, 11):
        bf = max(bf * (1 + tax) - pf, 0) if y <= n else 0
        bb = max(bb * (1 + bank) - pbk, 0) if y <= n else 0
        sf.append(bf)
        sb.append(bb)
        s += c["net"] - (pf if y <= n else 0)
        cum.append(s)
    st.subheader(L("Saldo devedor|Outstanding balance|Saldo deudor|未偿余额"))
    st.line_chart({"Fiagro": sf, L("Banco|Bank|Banco|银行"): sb})
    st.subheader(L("Saldo acumulado com Fiagro|Cumulative balance with Fiagro|Saldo acumulado con Fiagro|使用Fiagro的累计余额"))
    st.bar_chart(cum)
    st.caption(L("Parcela (Price) = P × i ÷ (1 − (1+i)^−n). Linhas como Plano Safra e BNDES podem ter taxas menores; compare.|Payment (Price) = P × i ÷ (1 − (1+i)^−n). Lines like Plano Safra and BNDES may have lower rates; compare.|Cuota (Price) = P × i ÷ (1 − (1+i)^−n). Líneas como Plano Safra y BNDES pueden tener tasas menores; compara.|还款额 = P × i ÷ (1 − (1+i)^−n)。Plano Safra和BNDES等可能利率更低，请比较。"))


def page_impact():
    st.header(L("Impacto e ODS|Impact and SDGs|Impacto y ODS|影响与可持续发展目标"))
    u = st.session_state.user
    rows = db.execute("select name,mwh,saving,co2,payback from projects where email=?", (u["email"],)).fetchall()
    if rows:
        st.metric(L("Energia total|Total energy|Energía total|总发电量"), "{:,.0f} MWh/{}".format(sum(r[1] for r in rows), L("ano|year|año|年")))
        st.metric("CO₂", "{:.1f} t/{}".format(sum(r[3] for r in rows), L("ano|year|año|年")))
        st.dataframe([{L("Projeto|Project|Proyecto|项目"): r[0], "MWh": round(r[1]), "R$/ano": round(r[2]), "CO₂ t": round(r[3], 1), "Payback": r[4]} for r in rows], hide_index=True)
    else:
        st.info(L("Salve um projeto na etapa Viabilidade.|Save a project in the Feasibility step.|Guarda un proyecto en el paso Viabilidad.|请在可行性步骤中保存项目。"))
    st.write(L("**ODS 7** Energia limpa e acessível|**SDG 7** Affordable and clean energy|**ODS 7** Energía asequible y limpia|**SDG 7** 经济适用的清洁能源"))
    st.write(L("**ODS 9** Indústria, inovação e infraestrutura|**SDG 9** Industry, innovation and infrastructure|**ODS 9** Industria, innovación e infraestructura|**SDG 9** 产业、创新和基础设施"))
    st.write(L("**ODS 12** Consumo e produção responsáveis|**SDG 12** Responsible consumption and production|**ODS 12** Producción y consumo responsables|**SDG 12** 负责任的消费和生产"))


# ---------- Investidor ----------
def page_projects():
    st.header(L("Projetos de biomassa (exemplos)|Biomass projects (examples)|Proyectos de biomasa (ejemplos)|生物质项目（示例）"))
    st.dataframe([
        {"": "EXEMPLO 1", L("Biomassa|Biomass|Biomasa|生物质"): L(BIO[0][0]), L("Retorno est.|Est. return|Retorno est.|预计回报"): "12% a.a.", L("Risco|Risk|Riesgo|风险"): L("Médio|Medium|Medio|中")},
        {"": "EXEMPLO 2", L("Biomassa|Biomass|Biomasa|生物质"): L(BIO[3][0]), L("Retorno est.|Est. return|Retorno est.|预计回报"): "11% a.a.", L("Risco|Risk|Riesgo|风险"): L("Baixo|Low|Bajo|低")},
        {"": "EXEMPLO 3", L("Biomassa|Biomass|Biomasa|生物质"): L(BIO[4][0]), L("Retorno est.|Est. return|Retorno est.|预计回报"): "14% a.a.", L("Risco|Risk|Riesgo|风险"): L("Alto|High|Alto|高")},
    ], hide_index=True, use_container_width=True)
    st.caption(L("Dados de exemplo, não são projetos reais.|Example data, not real projects.|Datos de ejemplo, no son proyectos reales.|示例数据，并非真实项目。"))


def page_invest():
    st.header(L("Simulador de rendimento|Yield simulator|Simulador de rendimiento|收益模拟"))
    ap = st.number_input(L("Quanto quer investir (R$)|Amount to invest (R$)|Cuánto invertir (R$)|投资金额 (R$)"), 100, 10000000, 10000, 500)
    y = st.slider(L("Rendimento anual (%)|Annual yield (%)|Rendimiento anual (%)|年收益率 (%)"), 4.0, 20.0, 12.0, 0.5)
    st.metric(L("Renda por mês|Income per month|Renta por mes|每月收入"), money(ap * y / 100 / 12))
    st.warning(L("Investir envolve risco de perda. Cotas de Fiagro são compradas em corretoras autorizadas pela CVM.|Investing involves risk of loss. Fiagro shares are bought through CVM-authorized brokers.|Invertir implica riesgo de pérdida. Las cuotas de Fiagro se compran en corredoras autorizadas por la CVM.|投资有亏损风险。Fiagro份额需通过CVM授权的券商购买。"))
    st.link_button(L("Investir (site da CVM)|Invest (CVM website)|Invertir (sitio de la CVM)|投资（CVM网站）"), "https://www.gov.br/cvm")


def page_sources():
    st.header(L("Fontes|Sources|Fuentes|来源"))
    for s in ["EMBRAPA (2025)", "Agrolink (2020)", "Sigma Earth (2026)", "Ponto Invest (2020)", "Diário de Investimentos (2025)"]:
        st.write("• " + s)
    disclaimer()


# ---------- App ----------
if "user" not in st.session_state:
    auth()
else:
    u = st.session_state.user
    st.sidebar.write("👤 " + u["name"])
    if u["role"] == "producer":
        pages = {L("1. Biomassas|1. Biomass|1. Biomasas|1. 生物质"): page_bio,
                 L("2. Tecnologia|2. Technology|2. Tecnología|2. 技术"): page_tech,
                 L("3. Viabilidade|3. Feasibility|3. Viabilidad|3. 可行性"): page_viab,
                 L("4. Fiagro|4. Fiagro|4. Fiagro|4. Fiagro"): page_fiagro,
                 L("5. Impacto|5. Impact|5. Impacto|5. 影响"): page_impact}
    else:
        pages = {L("Projetos|Projects|Proyectos|项目"): page_projects,
                 L("Simulador|Simulator|Simulador|模拟器"): page_invest}
    pages[L("Fontes|Sources|Fuentes|来源")] = page_sources
    choice = st.sidebar.radio(L("Menu|Menu|Menú|菜单"), list(pages))
    if st.sidebar.button(L("Sair|Log out|Salir|退出")):
        del st.session_state["user"]
        st.rerun()
    st.title("🌱 Bioagro")
    pages[choice]()
    disclaimer()
