# <a href="chamazetu.com">chamaZetu</a>

---

<a href="chamazetu.com">chamaZetu</a> is a comprehensive digital solution designed to revolutionize the way chamas (community savings groups) in Kenya manage their finances and chama activities.Whether you're a chama manager organizing chama activities or a member actively contributing to savings, this platform provides secure, transparent, and efficient environment for all your financial needs.

## Purpose

---

The primary purpose of chamaZetu is to empower chamas by offering the following key features:

1. **Centralized Financial Management**

   - manage contributions, withdrawals, and investments with a unifed dashboard
   - keep track of chama activties, financial health, and growth.

2. **Inclusivity and Accessibility**

   - Create public chamas, allowing members from different locations to join.
   - Enable potential members to explore and join chamas online.

3. **Security and Trust** (mvp II)

   - Implement robust KYC protocols to verify member identities.
   - Foster trust within the community by ensurng authenticity.

4. **Collaboration and Communication** (mvp II)

   - Real-time chat functionality for chama members to discuss decisions ad collaborate effectively.
   - Assign secretarial roles for administrative tasks like minute-taking and reminders

5. **Financial Growth Opportunities**
   - Integrate an in-house money market fund, allowing chamas to earn daily interest on idle cash.
   - Optimize financial returns beyond traditional savings methods.

## Features

---

### Managers

- **Chama Creation**

  - Managers can create public chamas, allowing for members to join/participate from various locations. - Managers can create private chamas, allowing only for select known members to join/participate. - Set up chama rules, goals, and contribution schedules.

- **Member Management**

  - Verify member identities through KYC integration.
  - Assign secretarial roles for administrative tasks.

- **Financial Tracking**
  - Commit idle cash to the in-house mmf as well as withdraw from the investment.
  - Monitor contributions, withdrawals, and overall chama growth.
  - Generate financial/chama reports and analytics.

### Members

- **Join Public Chamas**

  - Explore and join chamas based on interests and goals.
  - Participate in discussions and decision-making through in-chat communication.

- **Join Private Chamas**

  - Receive private chamas links, verify and join a chama.
  - Participate in discussions and decision-making through in-chat communication.

- **Secure Transactions**
  - Make contributions and withdrawals securely.
  - View chama savings/investment progress.

## Technologies Used

---

- **Backend**: FastAPI
- **Frontend**: Django
- **Database**: PostgreSQL (supabase-hosted)
- **Deployment**: GCP
- **Web Server**: Nginx
- **Message Broker**: Redis
- **Background Tasks**: Celery and Celery Beat
- **Payment Solution**: Integrated M-Pesa Daraja API
- **Contanerization**: Docker and Docker-compose

## Coming Soon (Past MVP 1 Features)

- chama Boost - After certain period of operation, chamas will have access to loans to boost their activities.
- loan management - Enable chamas to provide loans to members.
- Investment Recommendations - Introduce new investment vehicles for chamas and offer personalized investment advice.
- Advanced Analytics - Provide deeper insighs into chama performance.
