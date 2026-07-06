# 🔔 24x7 Telegram Alerts (PC/Laptop OFF hone par bhi)

Streamlit app (`app.py`) sirf tab tak scan karta hai jab tak wo browser me
khula hai. Agar aapka **PC band ho ya browser tab band ho, to Streamlit
alerts rukk jaate hain.**

Iske liye alag se `alert_bot.py` banaya gaya hai jo **GitHub Actions** ke
zariye GitHub ke apne server par chalta hai - free, aur aapka PC ON hona
zaroori nahi.

---

## Setup - ek baar karna hai

### 1. Repo GitHub par push karo
Agar already GitHub repo hai (README me mention hai) to bas ye naye files
add kar do:
```
alert_bot.py
.github/workflows/scan.yml
```

```bash
git add alert_bot.py .github/workflows/scan.yml
git commit -m "Add 24x7 Telegram alert bot"
git push
```

### 2. Telegram Bot Token & Chat ID GitHub Secrets me daalo
1. GitHub repo kholo → **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** par click karo, 2 secrets banao:
   - `TELEGRAM_BOT_TOKEN` → apna Bot Token
   - `TELEGRAM_CHAT_ID` → apna Chat ID

(Same token/chat-id jo aap Streamlit app ki sidebar me daalte ho.)

### 3. Apni ticker/timeframe list set karo
`alert_bot.py` file me upar **CONFIG** section me `TICKERS` aur `INTERVALS`
list edit kar do - jitne chaho utne stocks daal sakte ho.

### 4. Workflow enable karo
GitHub repo → **Actions** tab → agar pehli baar hai to "I understand my
workflows, go ahead and enable them" par click karo. Bas - ab ye har 15
minute me khud chalega (`.github/workflows/scan.yml` me cron schedule hai,
chaho to `*/15` ko `*/5` ya `*/30` kar sakte ho).

Manually turant test karne ke liye: Actions tab → "Zone Scanner (Telegram
Alerts)" workflow → **Run workflow** button.

---

## Ye kaise kaam karta hai

- Har run me `alert_bot.py` sabhi TICKERS × INTERVALS scan karta hai
- Naya zone milne par, ya entered/SL/Target hit hone par Telegram par
  **chart image + detailed caption** turant bhej deta hai. Har alert me:
  - Symbol, Timeframe, Pattern, Type (Supply/Demand)
  - Proximal, Distal (aur Target jab relevant ho)
  - Leg-out Formed (date/time jab wo candle bani)
  - Base Count (1/2/3 base candles)
  - Leg-out Count (1 ya 2 candles ka leg-out)
  - Chart me candles + zone box + proximal/distal/target lines dikhti hain
- `alerted_state.json` file me already-bheje-gaye alerts yaad rakhta hai
  (aur GitHub repo me commit ho jaati hai) - isliye **same alert dobara
  nahi aayega**
- Ye poori tarah GitHub ke server par chalta hai - aapka PC/phone/browser
  kuch bhi band ho, koi farak nahi padta

## Limitations (important - inhe samajh lena)

- ⏱️ GitHub Actions ka free cron **exactly punctual nahi hota** - kabhi
  kabhi 5-10 minute tak delay ho sakta hai, especially busy times pe.
  Real-time (second-by-second) alert ke liye ye tool nahi hai - lekin
  15-30 minute ke andar zone/SL/Target ka pata chal jayega.
- 💤 Agar repo me **60 din tak koi bhi activity/commit na ho**, GitHub
  automatically scheduled workflows ko disable kar deta hai. Kabhi kabhi
  ek chhota commit push kar dena (ya Actions tab se manually re-enable
  karna) isse bachne ke liye.
- 🌐 Yahoo Finance (`yfinance`) kabhi-kabhi rate-limit ya temporary error de
  sakta hai - script us combo ko skip kar dega aur agle run me phir try karega.
- Ye bot sirf **Telegram alerts** ke liye hai, chart/UI ke liye nahi -
  chart dekhne ke liye Streamlit app (`app.py`) hi use karo.
