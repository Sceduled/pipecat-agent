# Kakkamutta Platform: How It Works (Simple Version)

*(Note: because of you are dump ass I am not using techinical terms)*

Welcome to the simple guide! This document explains what we built and how all the moving pieces talk to each other to make the magic happen.

---

## 1. The Big Picture: What is this project?
At its core, we built a **Control Room for Phone Robots**. 

Normally, if you want an AI to talk on the phone, you have to write complex code for every single phone call. Instead, we built a beautiful **Dashboard** (the control room) where you can build, tweak, and launch different "Robot Personalities" with just a few clicks. 

---

## 2. The Dashboard (The Control Room)
The Dashboard is the shiny, beautiful website you log into. Think of it like a video game character creator. 

In the Dashboard, you can:
- **Give the Robot a Brain:** You type in rules like *"You are a polite real estate agent. Try to book a site visit."* 
- **Give the Robot a Voice:** You pick if it sounds like Priya, Bulbul, or Arjun.
- **Give the Robot Memories:** You can upload a PDF document (like a pricing menu or FAQs). The robot instantly memorizes it and will answer questions based on that document.
- **Trigger Phone Calls:** You can literally type in a phone number, hit "Call", and the robot will immediately pick up a real-world phone and call that person.

---

## 3. The Database (The Filing Cabinet)
Every time you create a new Robot Personality in the dashboard, that information is saved in our **Database**. 
Think of the Database as an infinite filing cabinet in the cloud. 

When you change a robot's name or upload a new PDF, the filing cabinet updates. 

The coolest part? **The Call Logs**. 
Every single time a robot finishes a phone call, it writes down everything that was said (like a movie script) and shoves it into the filing cabinet. When you go to the "Call Logs" tab in your Dashboard, it opens the cabinet and shows you the script of the call!

---

## 4. How a Phone Call Actually Works (The Journey)
Let's say a customer calls one of your phone numbers. Here is the journey of what happens in the span of `0.2` seconds:

1. **The Phone Rings:** The customer dials a real-world phone number. 
2. **The Switchboard (Vobiz):** A company called Vobiz catches the phone call and immediately routes the audio over the internet to our server.
3. **The Brain Check:** Our server answers the call and instantly checks the Filing Cabinet. It asks: *"Wait, which robot is assigned to this phone number?"*
4. **The Ear (Deepgram):** The customer says "Hello?". We use a tool called Deepgram to instantly turn their voice into text.
5. **The Brain (OpenAI/ChatGPT):** We send that text to the robot's brain. The brain looks at the rules you set in the Dashboard, reads the PDF you uploaded, and decides how to reply.
6. **The Mouth (Sarvam):** The brain generates a text reply. We send that text to a tool called Sarvam, which instantly reads it out loud in a human-sounding voice.
7. **The Reply:** The voice is sent back across the internet, through Vobiz, and into the customer's ear.

All of this happens back-and-forth instantly, creating a fluid, human-like conversation!
