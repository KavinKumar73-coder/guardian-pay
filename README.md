# 🛡️ Guardian Pay
### AI-Powered Payment Scam Detection & Protection System

**Guardian Pay** is an AI-powered payment protection system designed to identify potentially fraudulent transactions before payment processing. By combining Google Gemini AI, rule-based risk assessment, and PayPal integration, it helps users evaluate payment risks and make safer payment decisions.

The system analyzes payment details, generates a risk score, identifies suspicious indicators, and determines whether a transaction should proceed, require additional approval, or be blocked.

---

## 🚀 Key Features

- **🤖 AI-Powered Scam Detection** – Uses Google Gemini AI to analyze payment descriptions and identify potential scam indicators.
- **📊 Risk Scoring** – Generates a risk score between 0 and 100 to represent the potential risk of a transaction.
- **⚖️ Intelligent Payment Decisions** – Classifies transactions into three decision levels:
  - 🟢 `AUTO_PAY` – Low-risk transactions can proceed to the PayPal checkout flow.
  - 🟡 `HOLD` – Transactions requiring additional guardian approval are placed on hold.
  - 🔴 `BLOCK` – High-risk transactions are blocked to prevent potentially fraudulent payments.
- **💳 PayPal Integration** – Integrates PayPal for order creation and payment capture.
- **🔍 Risk Explanations** – Provides detected warning signs, risk indicators, and recommendations.
- **🔐 Environment-Based Configuration** – Uses environment variables to manage API credentials.

---

## 🧠 How It Works

1. **Payment Input:** The user enters payment information, including the recipient, amount, and payment description.
2. **AI Analysis:** Google Gemini AI analyzes the transaction details and identifies potential scam indicators.
3. **Risk Assessment:** The system combines AI analysis with predefined rule-based checks.
4. **Decision Engine:** The transaction receives one of three decisions:
   - `AUTO_PAY`
   - `HOLD`
   - `BLOCK`
5. **Payment Processing:** Eligible transactions proceed through the PayPal checkout and authorization flow. Transactions requiring approval are held, while blocked transactions cannot proceed.

---

## 🏗️ System Architecture

```text
              USER
                |
                v
        Payment Information
                |
                v
         Flask Application
                |
                v
       Gemini AI Analysis
                |
                v
       Rule-Based Assessment
                |
                v
         Decision Engine
                |
        +-------+-------+
        |       |       |
        v       v       v
     AUTO_PAY  HOLD   BLOCK
        |       |       |
        v       v       v
      PayPal  Guardian  Payment
      Checkout Approval Blocked
        |
        v
   Payment Authorization
        |
        v
   Payment Capture
```

---

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| Flask | Backend web framework |
| Google Gemini API | AI-based payment risk analysis |
| PayPal REST API | Payment order creation and capture |
| HTML | Webpage structure |
| CSS | User interface styling |
| JavaScript | Frontend interactions |
| python-dotenv | Environment variable management |

---

## 📁 Project Structure

```text
guardian-pay/
│
├── app.py
├── ai_scorer.py
├── rules.py
├── paypal.py
├── requirements.txt
├── .env.example
├── README.md
│
└── templates/
    └── ...
```

---

## ⚙️ Installation & Setup

Follow these steps to run Guardian Pay locally.

### 1. Clone the repository

```bash
git clone https://github.com/KavinKumar73-coder/guardian-pay.git
```

### 2. Navigate to the project directory

```bash
cd guardian-pay
```

### 3. Create a virtual environment

```bash
python -m venv .venv
```

### 4. Activate the virtual environment

**Windows PowerShell:**

```powershell
.venv\Scripts\Activate.ps1
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Configure environment variables

Create a `.env` file in the project root using `.env.example` as a reference.

Add your own API credentials to the `.env` file.

**Never upload your actual `.env` file or API credentials to GitHub.**

### 7. Start the application

```bash
python app.py
```

### 8. Open the application

Visit the following address in your browser:

http://127.0.0.1:5000

---

## 🎯 Payment Decision Examples

| Decision | Risk Level | System Action |
|---|---|---|
| AUTO_PAY | Low | Proceed to PayPal checkout |
| HOLD | Medium | Require guardian approval |
| BLOCK | High | Block the transaction |

The final decision depends on the AI-generated risk assessment and predefined application rules.

---

## 🔐 Security Considerations

- Sensitive API credentials are managed through environment variables.
- The `.env.example` file contains configuration placeholders rather than actual secrets.
- Payment processing uses the PayPal API.
- AI analysis failures should not result in automatic payment approval.

**Note:** Guardian Pay is a prototype developed for demonstration purposes. It is not a certified fraud detection service or a guarantee against financial losses. AI-generated risk assessments may not always be accurate.

---

## 🎥 Project Demonstration

Watch the working demonstration of Guardian Pay:

▶️ **[Watch Guardian Pay Demo on YouTube](https://youtu.be/DDnPVU8UFyY)**

---

## 👨‍💻 Developer

**Kavin Kumar**

Computer Science and Engineering Student

GitHub: [@KavinKumar73-coder](https://github.com/KavinKumar73-coder)

---

## 💡 Project Goal

To explore how Artificial Intelligence and payment gateway integration can work together to identify suspicious payment activity and introduce an additional layer of protection before transactions are processed.

---

**Guardian Pay 🛡️ — Think Before You Pay. Stay Protected.**