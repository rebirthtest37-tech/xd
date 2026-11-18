import discord
from discord import app_commands
from discord.ext import commands
import os
import psycopg2
import random
import asyncio
from datetime import datetime, timedelta

# --- KONFIGURACJA ---
ID_KANAL_EKONOMIA = 1386424048270966820
EMOJI_KASA = "<a:kasa:1572561091014164580>"

# Linki do animacji (GIFY)
GIF_RULETKA = "https://cdn.discordapp.com/attachments/1386424048270966820/1572578321458397204/Td9fnldXXnoOJVy.gif"
GIF_ORZEL = "https://cdn.discordapp.com/attachments/1386424048270966820/1572578056042979411/5z6HiMsa.gif"
GIF_RESZKA = "https://cdn.discordapp.com/attachments/1386424048270966820/1572578114075103355/JfEnIU0b.gif"

# Konfiguracja ról do wypłat (!Odbierz) -> [ID Roli: Kwota]
SALARY_CONFIG = {
    1386424048220766372: 5500,  # Staff
    1386424048220766373: 3500,  # Policja
    1386424048220766374: 500    # Obywatel / Cywil
}

# Konfiguracja Sklepu z dedykowanymi ikonami i przypisaniem ról
SHOP_CONFIG = {
    "Bronie Palne": [
        {"nazwa": "mac-9", "cena": 1500, "rola_id": None, "emoji": "🔫"},
        {"nazwa": "pistol", "cena": 3000, "rola_id": None, "emoji": "🔫"}
    ],
    "Licencje": [
        {"nazwa": "licencja-bron", "cena": 5000, "rola_id": 1505624602083332100, "emoji": "📜"}
    ],
    "Domy": [
        {"nazwa": "apartament", "cena": 25000, "rola_id": None, "emoji": "🏠"}
    ],
    "Inne": [
        {"nazwa": "Amunicja", "cena": 200, "rola_id": None, "emoji": "🎒"}
    ]
}

# --- BAZA DANYCH ---
def get_db_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS economy (
        user_id BIGINT PRIMARY KEY,
        wallet BIGINT DEFAULT 0,
        last_collect TIMESTAMP,
        last_work TIMESTAMP
    )''')
    conn.commit()
    cur.close()
    conn.close()

class EconomyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        init_db()
        await self.tree.sync()

bot = EconomyBot()

def get_balance(user_id):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT wallet, last_collect, last_work FROM economy WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO economy (user_id, wallet) VALUES (%s, 0)", (user_id,))
        conn.commit()
        row = (0, None, None)
    cur.close()
    conn.close()
    return row

def update_balance(user_id, amount):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE economy SET wallet = wallet + %s WHERE user_id = %s", (amount, user_id))
    conn.commit()
    cur.close()
    conn.close()

# --- KOMENDA / ODBIERZ ---
@bot.hybrid_command(name="odbierz", description="Odbierz dzienne wynagrodzenie ze swoich ról")
async def odbierz(ctx: commands.Context):
    if ctx.channel.id != ID_KANAL_EKONOMIA:
        return await ctx.send(f"❌ Tej komendy możesz używać tylko na kanale <#{ID_KANAL_EKONOMIA}>.", ephemeral=True)

    wallet, last_collect, _ = get_balance(ctx.author.id)
    now = datetime.now()

    if last_collect and now - last_collect < timedelta(days=1):
        remains = timedelta(days=1) - (now - last_collect)
        hours, remainder = divmod(int(remains.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        return await ctx.send(f"❌ Kolejny dochód możesz odebrać za **{hours} godzin i {minutes} minut**.", ephemeral=True)

    total_added = 0
    lines = []
    for r_id, amount in SALARY_CONFIG.items():
        role = ctx.guild.get_role(r_id)
        if role and role in ctx.author.roles:
            total_added += amount
            lines.append(f"🟢 {role.mention} » **{amount:,} ZŁ**".replace(",", " "))

    if total_added == 0:
        return await ctx.send("❌ Nie posiadasz żadnej roli uprawniającej do pobrania wypłaty.", ephemeral=True)

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE economy SET wallet = wallet + %s, last_collect = %s WHERE user_id = %s", (total_added, now, ctx.author.id))
    conn.commit()
    cur.close()
    conn.close()

    embed = discord.Embed(title="📈 Przychód odebrany pomyślnie", color=discord.Color.green())
    embed.description = "\n".join(lines) + "\n\n─────────────────\n" + f"Suma: + {EMOJI_KASA} **{total_added:,} ZŁ**".replace(",", " ")
    await ctx.send(embed=embed)

# --- KOMENDA / PRACUJ ---
@bot.hybrid_command(name="pracuj", description="Zarób dodatkowe PLN-y")
async def pracuj(ctx: commands.Context):
    if ctx.channel.id != ID_KANAL_EKONOMIA:
        return await ctx.send(f"❌ Tej komendy możesz używać tylko na kanale <#{ID_KANAL_EKONOMIA}>.", ephemeral=True)

    _, _, last_work = get_balance(ctx.author.id)
    now = datetime.now()

    if last_work and now - last_work < timedelta(hours=4):
        remains = timedelta(hours=4) - (now - last_work)
        hours, remainder = divmod(int(remains.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        return await ctx.send(f"⏳ Jesteś zmęczony! Następna praca za **{hours}h {minutes}m**.", ephemeral=True)

    zarobek = random.randint(100, 500)
    teksty_pracy = [
        f"💼 Pracowałeś u pani która zapłaciła ci {EMOJI_KASA} **{zarobek} ZŁ**",
        f"🏗️ Pracowałeś na budowie i zarobiłeś {EMOJI_KASA} **{zarobek} ZŁ**",
        f"📦 Rozwoziłeś paczki i dostałeś {EMOJI_KASA} **{zarobek} ZŁ**",
        f"🏪 Pomagałeś w sklepie i zarobiłeś {EMOJI_KASA} **{zarobek} ZŁ**"
    ]
    opis = random.choice(teksty_pracy)

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE economy SET wallet = wallet + %s, last_work = %s WHERE user_id = %s", (zarobek, now, ctx.author.id))
    conn.commit()
    cur.close()
    conn.close()

    wallet, _, _ = get_balance(ctx.author.id)
    embed = discord.Embed(title="⛏️ Dniówka ukończona!", description=f"{opis}\n\n─────────────────\nZarób więcej za 4 godziny\nSaldo: {EMOJI_KASA} **{wallet:,} ZŁ**".replace(",", " "), color=discord.Color.teal())
    await ctx.send(embed=embed)

# --- KOMENDA / PORTFEL ---
@bot.hybrid_command(name="portfel", description="Sprawdź stan swojego konta")
async def portfel(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    wallet, _, _ = get_balance(target.id)
    embed = discord.Embed(title=f"💳 Portfel: {target.display_name}", description=f"Stan konta: {EMOJI_KASA} **{wallet:,} ZŁ**".replace(",", " "), color=discord.Color.purple())
    await ctx.send(embed=embed)

# --- SYSTEM SKLEPU ---
class ShopSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Bronie Palne", emoji="🔫"),
            discord.SelectOption(label="Licencje", emoji="📜"),
            discord.SelectOption(label="Domy", emoji="🏠"),
            discord.SelectOption(label="Inne", emoji="📦")
        ]
        super().__init__(placeholder="Wybierz kategorię sklepu...", options=options)

    async def callback(self, interaction: discord.Interaction):
        cat = self.values[0]
        items = SHOP_CONFIG.get(cat, [])
        opis = "\n".join([f"{item['emoji']} **{item['nazwa']}** — {EMOJI_KASA} **{item['cena']:,} ZŁ**".replace(",", " ") for item in items]) or "Brak produktów."
        embed = discord.Embed(title=f"🛒 Sklep - {cat}", description=f"{opis}\n\n─────────────────\n*Użyj komendy `!Kup [Dokładna nazwa]` aby dokonać zakupu.*", color=discord.Color.orange())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(ShopSelect())

@bot.hybrid_command(name="sklep", description="Otwórz sklep z przedmiotami")
async def sklep(ctx: commands.Context):
    if ctx.channel.id != ID_KANAL_EKONOMIA:
        return await ctx.send(f"❌ Tej komendy możesz używać tylko na kanale <#{ID_KANAL_EKONOMIA}>.", ephemeral=True)
    
    embed = discord.Embed(title="🛒 SKLEP VESPER RP", description="Wybierz interesującą Cię kategorię z menu poniżej:", color=discord.Color.orange())
    await ctx.send(embed=embed, view=ShopView())

@bot.hybrid_command(name="kup", description="Kup przedmiot ze sklepu")
async def kup(ctx: commands.Context, *, nazwa: str):
    if ctx.channel.id != ID_KANAL_EKONOMIA:
        return await ctx.send(f"❌ Tej komendy możesz używać tylko na kanale <#{ID_KANAL_EKONOMIA}>.", ephemeral=True)

    przedmiot = None
    for kat, items in SHOP_CONFIG.items():
        for item in items:
            if item["nazwa"].lower() == nazwa.lower():
                przedmiot = item
                break
        if przedmiot: break

    if not przedmiot:
        return await ctx.send("❌ Taki przedmiot nie istnieje w sklepie.", ephemeral=True)

    wallet, _, _ = get_balance(ctx.author.id)
    if wallet < przedmiot["cena"]:
        return await ctx.send(f"❌ Nie masz wystarczająco środków w portfelu! Brakuje Ci **{(przedmiot['cena'] - wallet):,} ZŁ**.".replace(",", " "), ephemeral=True)

    update_balance(ctx.author.id, -przedmiot["cena"])

    if przedmiot["rola_id"]:
        role = ctx.guild.get_role(przedmiot["rola_id"])
        if role:
            try:
                await ctx.author.add_roles(role)
            except:
                pass

    await ctx.send(f"✅ Pomyślnie zakupiono **{przedmiot['nazwa']}** {przedmiot['emoji']} za {EMOJI_KASA} **{przedmiot['cena']:,} ZŁ**!".replace(",", " "))

# --- RULETKA Z ANIMACJĄ ---
@bot.hybrid_command(name="ruletka", description="Zagraj w ruletkę")
async def ruletka(ctx: commands.Context, kwota: int, kolor: str, numerek: int = None):
    if ctx.channel.id != ID_KANAL_EKONOMIA:
        return await ctx.send(f"❌ Tej komendy możesz używać tylko na kanale <#{ID_KANAL_EKONOMIA}>.", ephemeral=True)

    wallet, _, _ = get_balance(ctx.author.id)
    if kwota <= 0 or wallet < kwota:
        return await ctx.send("❌ Nie masz tyle pieniędzy w portfelu lub podano złą kwotę.", ephemeral=True)

    kolor = kolor.lower()
    if kolor not in ["czerwony", "czarny"]:
        return await ctx.send("❌ Wybierz prawidłowy kolor: `czerwony` lub `czarny`.", ephemeral=True)

    embed_start = discord.Embed(title="🎰 Kasyno Vesper", description="Krupier kręci kołem ruletki... Trwa losowanie!", color=discord.Color.dark_magenta())
    embed_start.set_image(url=GIF_RULETKA)
    msg = await ctx.send(embed=embed_start)
    
    await asyncio.sleep(4.0)
    
    wylosowany_kolor = random.choice(["czerwony", "czarny"])
    wylosowana_liczba = random.randint(0, 36)

    wygrana = 0
    if kolor == wylosowany_kolor:
        wygrana = kwota * 2

    if numerek is not None and numerek == wylosowana_liczba:
        wygrana = kwota * 14

    embed_result = discord.Embed(title="🎰 Wynik Ruletki", color=discord.Color.green() if wygrana > 0 else discord.Color.red())
    
    if wygrana > 0:
        update_balance(ctx.author.id, wygrana - kwota)
        embed_result.description = f"🎉 Wylosowano: **{wylosowany_kolor.upper()} ({wylosowana_liczba})**!\n\nWygrana: {EMOJI_KASA} **{wygrana:,} ZŁ**!".replace(",", " ")
    else:
        update_balance(ctx.author.id, -kwota)
        embed_result.description = f"😢 Wylosowano: **{wylosowany_kolor.upper()} ({wylosowana_liczba})**.\n\nPrzegrałeś: {EMOJI_KASA} **{kwota:,} ZŁ**.".replace(",", " ")
        
    await msg.delete()
    await ctx.send(embed=embed_result)

# --- RZUT MONETĄ Z ANIMACJĄ ---
@bot.hybrid_command(name="moneta", description="Zagraj w rzut monetą (50/50)")
async def moneta(ctx: commands.Context, kwota: int, wybor: str):
    if ctx.channel.id != ID_KANAL_EKONOMIA:
        return await ctx.send(f"❌ Tej komendy możesz używać tylko na kanale <#{ID_KANAL_EKONOMIA}>.", ephemeral=True)

    wallet, _, _ = get_balance(ctx.author.id)
    if kwota <= 0 or wallet < kwota:
        return await ctx.send("❌ Nie masz tyle pieniędzy w portfelu.", ephemeral=True)

    wybor = wybor.lower()
    if wybor not in ["orzel", "reszka"]:
        return await ctx.send("❌ Wybierz `orzel` lub `reszka`.", ephemeral=True)

    embed_start = discord.Embed(title="🪙 Rzut Monetą", description="Moneta szybuje wysoko w górę... obracając się!", color=discord.Color.gold())
    embed_start.set_image(url=GIF_ORZEL)
    msg = await ctx.send(embed=embed_start)
    
    await asyncio.sleep(3.0)
    
    wynik = random.choice(["orzel", "reszka"])
    gif_wynik = GIF_ORZEL if wynik == "orzel" else GIF_RESZKA

    embed_result = discord.Embed(title=f"🪙 Wynik rzutu: {wynik.upper()}", color=discord.Color.green() if wybor == wynik else discord.Color.red())
    embed_result.set_image(url=gif_wynik)

    if wybor == wynik:
        update_balance(ctx.author.id, kwota)
        embed_result.description = f"🎉 Doskonały strzał! Wygrałeś {EMOJI_KASA} **{(kwota * 2):,} ZŁ**!".replace(",", " ")
    else:
        update_balance(ctx.author.id, -kwota)
        embed_result.description = f"😢 Niestety tym razem pech! Przegrałeś {EMOJI_KASA} **{kwota:,} ZŁ**.".replace(",", " ")

    await msg.delete()
    await ctx.send(embed=embed_result)

@bot.event
async def on_ready():
    print(f"🤖 Bot Ekonomii zalogowany jako {bot.user}")

bot.run(os.getenv("DISCORD_TOKEN"))
