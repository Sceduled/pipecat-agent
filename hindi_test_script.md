# 📞 Multilingual Hindi Test Script

This script is written phonetically (Hindi words using English letters). You can read the **"YOU"** sections out loud during your test call. 

The **"AI AGENT"** sections show what the AI is *likely* to say, so you know exactly when it's your turn to speak. I have also included English translations so you know what is happening.

---

### Step 1: The Introduction
**🤖 AI AGENT:** 
> "Namaste, kya meri baat Adithya se ho rahi hai? Main Prestige Realty se Priya bol rahi hoon."
> *(Meaning: Hello, am I speaking with Adithya? I am Priya from Prestige Realty.)*

**🗣️ YOU:**
> "Haa, main Adithya bol raha hu."
> *(Meaning: Yes, I am Adithya speaking.)*

---

### Step 2: Asking for Time
**🤖 AI AGENT:** 
> "Ji zaroor... kya aapke paas thoda waqt hai baat karne ke liye?"
> *(Meaning: Sure... do you have a little time to talk?)*

**🗣️ YOU:**
> "Haa, bataiye."
> *(Meaning: Yes, tell me.)*

---

### Step 3: Requirements & Code-Switching Test
**🤖 AI AGENT:** 
> "Thik hai, main check karti hu... Aapko Whitefield mein 3 BHK chahiye tha. Kya aap apna budget bata sakte hain?"
> *(Meaning: Okay, I am checking... You wanted a 3 BHK in Whitefield. Can you tell me your budget?)*

**🗣️ YOU:** *(Switching completely to English here!)*
> "My budget is around ninety lakhs to one crore."

---

### Step 4: Property Details
**🤖 AI AGENT:** 
> "Samajh gayi, main details dekhti hu... Mere paas Whitefield mein Prestige Lakeside Habitat hai. Iska price 85 lakhs hai aur isme clubhouse aur pool bhi hai."
> *(Meaning: Understood, let me check the details... I have Prestige Lakeside Habitat in Whitefield. Its price is 85 lakhs and it has a clubhouse and pool.)*

**🗣️ YOU:**
> "Thik hai, kya main Sunday ko property dekhne aa sakta hu?"
> *(Meaning: Okay, can I come see the property on Sunday?)*

---

### Step 5: Booking the Visit
**🤖 AI AGENT:** 
> "Ji bilkul... aap kis waqt aana chahenge?"
> *(Meaning: Yes absolutely... what time would you like to come?)*

**🗣️ YOU:** 
> "Morning, eleven AM."

---

### Step 6: Confirmation & Goodbye
**🤖 AI AGENT:** 
> "Thik hai Adithya, aapka site visit Sunday subah gyarah baje ke liye book ho gaya hai. Thank you!"
> *(Meaning: Okay Adithya, your site visit is booked for Sunday morning at eleven o'clock. Thank you!)*

**🗣️ YOU:** 
> "Thank you, bye."

---

### ▶️ How to start the call:
Copy and paste this into your PowerShell terminal:
```powershell
Invoke-RestMethod -Method POST -Uri "https://kakamutta-production.up.railway.app/dial-multilingual" -ContentType "application/json" -Body '{"to":"+919360099125","name":"Adithya","call_type":"follow_up","interest":"3BHK in Whitefield"}'
```
