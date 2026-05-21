"""
business_docs_pairs.py
Converts the free business document library system into structured training Q&A pairs.
Appends to training_data/business_docs_training.jsonl (deduped).
Run: python training_data/business_docs_pairs.py
"""
import json
from pathlib import Path

OUT = Path(__file__).parent / "business_docs_training.jsonl"

PAIRS = [
    # ── MASTER FREE RESOURCE LIBRARIES ───────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What are the best free government and nonprofit resources for running a business from start to close?"},
            {"role": "assistant", "content": """The following free resources cover the complete business lifecycle — start, launch, manage, grow, fund, comply, and close. These are primary sources, not aggregators, which means the information is authoritative and regularly updated.

SBA Business Guide (sba.gov): The best all-around free guide for the full business lifecycle. Covers market research, business plans, startup costs, funding, entity structure, registration, licenses, bank accounts, insurance, taxes, compliance, marketing, cybersecurity, disasters, exporting, contracting, selling, and closing.

SBA 10 Steps to Start Your Business: A practical checklist for moving from idea to legal launch — market research, business plan, funding, location, structure, name, registration, tax IDs, permits, and bank account.

SCORE Templates Library (score.org): Free templates for business plans, startup expenses, financial projections, cash flow, profit-and-loss projections, SWOT analysis, marketing plans, and established-business growth planning. SCORE also provides free mentoring.

IRS Small Business and Self-Employed Tax Center (irs.gov): Free tax forms, publications, recordkeeping guidance, EIN info, self-employment tax resources, and operating/closing business tax guidance. IRS Publication 583 covers starting a business and keeping records. IRS Publication 15 covers employer payroll tax responsibilities.

USA.gov Small Business: Free government starting point for starting, funding, managing, importing, and exporting a business.

SBA Learning Platform: Free training programs for business owners at different stages, including growth, contracting, and development programs.

America's SBDC Network (americassbdc.org): Free or low-cost business counseling and training through Small Business Development Centers — an SBA partner serving aspiring and existing entrepreneurs.

FTC Business Guidance (ftc.gov): Free plain-language legal compliance guidance for advertising, marketing, privacy, security, consumer protection, scams, online sales, and data practices.

Department of Labor Wage and Hour Division Small Business Resources (dol.gov/whd): Free employer compliance toolkits, fact sheets, FAQs, posters, and wage/hour guidance.

EEOC Small Business Resource Center (eeoc.gov): Free employment discrimination, hiring, workplace policy, poster, and recordkeeping guidance for small employers.

OSHA Small Business Resources (osha.gov): Free workplace safety and health resources, small business safety handbook, compliance guides, recordkeeping, and no-cost confidential consultation.

Census Business Builder (census.gov): Free market research tool for identifying customers, competitors, locations, demographics, and expansion opportunities.

NIST Small Business Cybersecurity Corner (nist.gov): Free cybersecurity guides, quick-start resources, and frameworks for small businesses.

CISA Cyber Guidance for Small Businesses (cisa.gov): Free role-based cybersecurity action plans and security guidance for small businesses.

USPTO Trademark Basics and Basic Facts About Trademarks (uspto.gov): Free trademark education for choosing, protecting, and registering business names, logos, and brands before investing in them.

U.S. Copyright Office Resources (copyright.gov): Free copyright explanations, FAQs, registration guidance, and fair use resources for creative assets, software, media, content, and brand materials.

International Trade Administration Export Resources (trade.gov): Free exporting guides, export plan resources, market research tools, export documentation guidance, and trade finance guides.

SAM.gov Entity Registration Checklist: Free official checklist for getting a Unique Entity ID and registering to do business with the federal government. SAM.gov registration and UEI are always free — never pay a third party for this.

Ready.gov Business Continuity Planning: Free business continuity plan document, business impact analysis guidance, and IT disaster recovery planning resources.

Best first move: Download the SBA Business Guide, SCORE business plan template, SCORE startup expenses template, SCORE financial projections template, IRS Publication 583, IRS Publication 334, and the DOL/EEOC/OSHA employer resources before creating anything else. Those give the foundation for planning, taxes, records, finances, legal setup, hiring, and compliance."""}
        ]
    },

    # ── STARTING A BUSINESS DOCS ──────────────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What documents do I need to start a business? Give me the complete list with what each one does."},
            {"role": "assistant", "content": """These are the foundational documents for starting a business, sequenced from idea validation through legal launch.

VALIDATION & PLANNING

Business idea validation worksheet: Answer these before spending money — problem, customer, solution, competitor alternatives, why now, willingness to pay, and first test. Use SBA market research guidance and Census Business Builder to validate demand, customer demographics, market size, and competitor presence.

Market research report: Document your target market, customer segments, location, pricing, demand, saturation, and buying behavior. SBA recommends market research to reduce risk and find a competitive advantage.

Competitive analysis worksheet: List competitors, prices, strengths, weaknesses, reviews, target customers, positioning, and gaps you can exploit. SBA pairs competitive analysis with market research as a core planning step.

Business plan: Use the SBA business plan guide or SCORE startup business plan template. Include executive summary, company description, market analysis, organization, products/services, marketing, operations, financials, and funding needs.

Lean startup one-page plan: Faster alternative — problem, solution, customers, channels, revenue streams, cost structure, key metrics, and advantage. SBA notes lean startup plans can be very short but must cover the most important elements.

FINANCIAL FOUNDATION

Startup expenses worksheet: Use SCORE's Startup Expenses template to estimate formation costs, equipment, inventory, technology, rent, marketing, licenses, insurance, payroll, professional services, and cash reserve.

Financial projections template: Use SCORE's template for startup expenses, payroll, sales forecast, operating expenses, cash flow, income statements, balance sheet, break-even analysis, ratios, COGS, amortization, and depreciation.

12-month cash flow statement: Track expected money coming in and going out, anticipate cash shortages, plan financing needs.

3-year cash flow statement: Required for lenders and investors; also useful for expansion planning and longer-term capital needs.

LEGAL STRUCTURE & IDENTITY

Business structure comparison document: Compare sole proprietorship, partnership, LLC, corporation, and S corporation by liability, taxes, control, paperwork, funding, and future growth. Structure affects both legal and tax treatment — SBA and IRS both explain this.

Business name checklist: Legal name, DBA/trade name, domain availability, social handles, state name search, trademark search, and brand risk. SBA's launch guidance includes choosing and registering the business name.

Trademark search and brand protection notes: Use USPTO Trademark Basics before investing heavily in a name, logo, slogan, product name, or brand identity. A trademark search before launch prevents expensive conflicts later.

REGISTRATION & COMPLIANCE

Business registration checklist: State registration, local registration, DBA, registered agent, ownership information, formation documents, and renewal dates. Requirements depend on location and business activities.

EIN application notes: Apply directly through IRS — it is free and takes minutes. The IRS explicitly warns that you never need to pay a fee for an EIN. Never use a third-party service for this.

License and permit checklist: Track federal, state, county, city, zoning, health, professional, sales tax, home occupation, and industry-specific permits. Both SBA and USA.gov emphasize that licensing requirements depend on industry, location, and activity.

Business bank account checklist: EIN, formation documents, ownership agreement, address, IDs, initial deposit, and authorized signers. SBA includes bank account setup as part of the launch process — required before accepting payments.

OWNERSHIP & PROTECTION

Insurance needs worksheet: List general liability, professional liability, product liability, commercial property, workers' compensation, cyber insurance, auto, key person, and business interruption coverage. SBA explains insurance helps protect against accidents, disasters, and lawsuits.

Operating agreement, bylaws, or partnership agreement: Create early to document ownership, voting rights, profit/loss splits, member roles, decision rules, buyout rules, dispute handling, and dissolution terms. State law governs these — get attorney review for complex ownership structures.

Founder agreement: If more than one founder exists, cover equity, vesting, IP ownership, roles, compensation, decision rights, founder exit, non-solicit limits where lawful, confidentiality, and deadlock resolution. Missing founder agreements are a leading cause of early company failure.

Intellectual property inventory: Track logos, code, website content, product designs, photos, videos, written material, trade secrets, domains, and licenses. Separate copyright (automatic, covers creative works), trademark (registered, covers brand identity), patent (applied for, covers inventions), and trade secret (contractual, covers proprietary processes) issues."""}
        ]
    },

    # ── DAILY OPERATIONS DOCS ─────────────────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What documents do I need to run daily business operations properly?"},
            {"role": "assistant", "content": """Daily operations documentation converts a business from founder-dependent to system-dependent. These documents are the operational infrastructure.

PROCESS DOCUMENTATION

Operations manual: How the business actually runs — opening/closing procedures, customer service standards, order processing, refunds, inventory, safety, cash handling, admin tasks, tech tools, escalation paths, and emergency contacts.

Standard operating procedures (SOPs): Write SOPs for every repeatable task: sales calls, client onboarding, order fulfillment, invoicing, payment collection, complaint handling, purchasing, quality checks, shipping, returns, data backups, and account access management. SOPs are the difference between a business that scales and one that breaks when you're unavailable.

FINANCIAL TRACKING

Chart of accounts: Accounting categories for income, cost of goods sold, payroll, software, rent, utilities, ads, contractors, equipment, travel, meals, taxes, insurance, interest, and owner draws. Required for coherent financial reporting.

Recordkeeping policy: IRS guidance states that good records help monitor business progress, prepare financial statements and tax returns, identify income sources, track deductible expenses, and support items reported on tax returns. The policy documents what gets kept, in what format, and for how long.

Transaction log: Consistent record of sales, refunds, expenses, invoices, receipts, deposits, owner contributions, owner draws, loans, and asset purchases. IRS guidance explains that business books should show gross income, deductions, and credits.

Receipt and expense documentation folder: Keep receipts, invoices, mileage records, bank statements, card statements, payroll records, inventory records, and asset purchase records. IRS Publication 583 explains recordkeeping examples for small businesses.

Tax calendar: Estimated tax payments, payroll tax deposits, sales tax due dates, annual reports, franchise taxes, 1099 deadlines, W-2 deadlines, and income tax deadlines. The IRS small business center includes filing and tax calendar resources.

Monthly financial review worksheet: Track revenue, gross margin, net profit, cash balance, accounts receivable, accounts payable, debt, customer acquisition cost, average order value, churn, and runway. Monthly reviews catch problems before they become crises.

FINANCIAL STATEMENTS

Balance sheet: Track assets, liabilities, and equity. SBA's finance guidance explains that a balance sheet helps account for costs and track what the business owns and owes.

Profit and loss statement: Use SCORE's 12-month profit-and-loss projection to forecast and track revenue and expenses.

Cash flow forecast: Use SCORE's 12-month or 3-year cash flow templates to anticipate cash shortages and capital needs. Cash flow management is survival management — profitable businesses fail when they run out of cash.

CUSTOMER TRANSACTIONS

Invoice template: Business name, address, invoice number, date, due date, customer info, scope, quantity, rate, taxes, payment methods, late fee terms, and remittance instructions.

Quote/proposal template: Scope, deliverables, assumptions, exclusions, timeline, pricing, revision limits, payment schedule, expiration date, and acceptance signature.

CONTRACTS

Customer contract or service agreement: Scope, pricing, payment terms, cancellation, refunds, warranties/disclaimers, IP ownership, confidentiality, limitation of liability, dispute process, and governing law. Use attorney review for higher-risk work.

Vendor agreement: Deliverables, pricing, payment terms, service levels, confidentiality, ownership of work, warranties, termination, insurance, compliance, and data security responsibilities.

Independent contractor agreement: Scope, contractor status (not employee), payment, deliverables, IP assignment, confidentiality, tools/equipment, tax responsibility, non-exclusivity, and termination. Contractor misclassification is a significant legal and tax risk.

POLICIES

Customer support policy: Response times, refund rules, replacement rules, complaint handling, escalation, chargeback handling, and documentation.

Refund and return policy: Especially important for e-commerce, subscriptions, physical goods, and services. Align with FTC advertising and consumer protection guidance — marketing claims must be truthful and not deceptive.

Privacy policy: Required or strongly expected if you collect personal information through a website, app, form, newsletter, CRM, payments, analytics, or customer accounts. FTC privacy and data security resources explain business responsibilities.

DATA SECURITY

Data inventory: What customer, employee, payment, health, financial, location, behavioral, and account data you collect; where it lives; who can access it; why you need it; and when it is deleted.

Access control list: Who has access to email, bank, accounting, payroll, website, domain, hosting, CRM, ads, cloud storage, password manager, social accounts, and admin systems. Review quarterly and revoke access immediately when employees or contractors leave."""}
        ]
    },

    # ── HIRING DOCS ───────────────────────────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What documents do I need for hiring employees legally and correctly?"},
            {"role": "assistant", "content": """Hiring creates legal obligations that persist for the life of the employment relationship and beyond. These documents cover the complete hiring lifecycle.

PRE-HIRE

Hiring checklist: Job description, pay range, interview process, background check rules, offer letter, tax forms, Form I-9, payroll setup, handbook, required posters, and onboarding steps.

Job description template: Title, duties, required skills, preferred skills, schedule, location, pay type, reporting manager, physical requirements if applicable, and equal employment opportunity language. EEO language is both a legal requirement for many employers and a signal of culture.

AT OFFER

Offer letter template: Position, compensation, start date, schedule, at-will status where applicable, contingencies, benefits, and acceptance signature. At-will status means the employer or employee can end the relationship at any time for any lawful reason — applicable in most U.S. states.

FIRST DAY — LEGALLY REQUIRED

Form I-9 (Employment Eligibility Verification): USCIS provides Form I-9 and a Handbook for Employers. Employers must verify identity and employment authorization for every employee hired in the United States. I-9 must be completed within three business days of the employee's start date.

Payroll tax enrollment: IRS Publication 15 explains employer responsibilities for withholding, depositing, reporting, paying, and correcting employment taxes. Includes federal income tax withholding, Social Security, Medicare (FICA), and Federal Unemployment Tax Act (FUTA) obligations.

Required workplace posters: DOL provides free electronic copies of required posters. The Poster Advisor tool helps employers determine which posters apply based on employer type, size, and location. Failing to post required notices is a compliance violation.

ONGOING EMPLOYER COMPLIANCE

Employee handbook: Cover attendance, pay periods, overtime, timekeeping, anti-harassment, discrimination, safety, data security, device use, social media, leave, benefits, discipline, termination, confidentiality, and complaint channels.

Anti-discrimination compliance notes: EEOC's Small Business Resource Center explains small business requirements, recordkeeping, required notices, workplace discrimination laws, and employer tips. Federal law prohibits discrimination based on race, color, religion, sex, national origin, age (40+), disability, and genetic information. State and local laws often add additional protected categories.

Wage and hour compliance file: Keep minimum wage, overtime, timekeeping, child labor, FMLA if applicable, contractor classification, and industry-specific materials. DOL Wage and Hour Division provides free compliance toolkits, fact sheets, FAQs, and training materials. Wage and hour violations are among the most common and expensive employer compliance problems.

Safety and health plan: OSHA provides small business safety resources, compliance guides, safety and health program materials, recordkeeping guidance, and no-cost confidential consultation. The OSHA consultation program is free and separate from enforcement — you can get an assessment without triggering an inspection.

KEY EMPLOYER COMPLIANCE AREAS

Overtime: Under the federal Fair Labor Standards Act, most employees who work more than 40 hours per week must receive overtime pay at 1.5x their regular rate. Some states have more protective overtime rules.

Contractor vs. employee classification: Misclassifying employees as independent contractors is a serious federal and state compliance risk. The DOL, IRS, and state agencies each have their own classification tests. When in doubt, the safer classification is employee.

FMLA (Family and Medical Leave Act): Applies to employers with 50 or more employees. Eligible employees can take up to 12 weeks of unpaid, job-protected leave for qualifying reasons. State and local FMLA equivalents often apply at smaller employer sizes.

Workers' compensation: Required in virtually every state. Covers employees injured on the job. Failure to carry required workers' compensation insurance is a serious legal and financial risk.

Payroll recordkeeping: IRS and state requirements govern how long payroll records must be retained. Generally, keep payroll tax records for at least 4 years after the due date of the tax or the date the tax was paid, whichever is later."""}
        ]
    },

    # ── COMPLIANCE & PROTECTION DOCS ─────────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What compliance and protection documents does a business need to stay legal and secure?"},
            {"role": "assistant", "content": """Compliance documentation creates the infrastructure that keeps the business legal, insured, secure, and operational through disruptions. These documents are rarely urgent — until they're critical.

ANNUAL COMPLIANCE TRACKING

Annual compliance calendar: Track state annual reports, registered agent renewal, business licenses, permits, insurance renewal, tax deadlines, payroll deadlines, OSHA logs if applicable, sales tax filings, contract renewals, lease dates, and domain renewals. SBA's legal compliance guidance notes that responsibilities depend on business type and location.

License renewal tracker: License number, agency, renewal date, fees, responsible person, supporting docs, and penalties for missing renewal. License lapses can void contracts, trigger fines, and in regulated industries, require stopping operations.

CONTRACT MANAGEMENT

Contract repository index: Keep customer contracts, vendor contracts, leases, loan docs, insurance policies, contractor agreements, NDAs, purchase orders, proposals, and amendments in one indexed folder. Organized contract management prevents disputes from turning into legal crises.

Insurance policy tracker: Policy type, carrier, broker, coverage limits, deductibles, exclusions, renewal date, certificate of insurance, and claims process. SBA's insurance guide is a free reference for identifying coverage categories. Review annually — coverage needs change as the business grows.

CYBERSECURITY

Cybersecurity plan: Use NIST Small Business Cybersecurity Corner and CISA Cyber Guidance for Small Businesses to build a plan covering accounts, multi-factor authentication, backups, phishing training, devices, software patching, Wi-Fi security, vendor access controls, incident response, and recovery.

Incident response plan: Define who to call, what to shut down, how to preserve evidence, how to communicate with customers, how to restore backups, and when to notify banks, insurers, platforms, customers, regulators, or law enforcement. Tested incident response plans reduce breach damage by an order of magnitude compared to ad hoc responses.

Password and account recovery document: Do not store plain-text passwords. Track where accounts exist, who owns them, recovery emails, MFA method, backup codes location, and emergency access procedure. This document prevents business lockout when a key person leaves or becomes unavailable.

BUSINESS CONTINUITY

Backup and disaster recovery plan: Ready.gov explains that data backup and recovery should be part of the business continuity plan and IT disaster recovery plan. The 3-2-1 rule: 3 copies of data, 2 different storage types, 1 offsite.

Business continuity plan: Ready.gov provides a free Business Continuity Plan document and guidance for organizing a continuity team, business impact analysis, recovery strategies, and testing. A BCP documents how the business operates during and after a disruption.

Business impact analysis: Ready.gov's BIA guidance helps estimate the consequences of disruption and gather information needed for recovery strategies. Identifies which functions are most critical and how long the business can operate without each one.

Emergency contact sheet: Employees, owners, vendors, landlord, insurance, bank, accountant, attorney, IT support, utility companies, key customers, emergency services, and platform support. Include backup contacts for each. Keep a printed copy offsite.

SBA Business Resilience Guide: SBA's resilience guide includes best practices and template forms for disaster preparation and recovery.

FTC DATA SECURITY

FTC data security checklist: Use FTC's "Protecting Personal Information" guide to design a security checklist around what data you collect, who has access, how it is stored, how it is protected, and how it is disposed of. The FTC can take action against businesses for failure to protect consumer data.

ADVERTISING & MARKETING COMPLIANCE

Advertising compliance checklist: FTC guidance states that advertising claims must be truthful, cannot be deceptive or unfair, and must be evidence-based. Use before publishing ads, landing pages, influencer promotions, testimonials, guarantees, pricing claims, or comparison claims.

Email marketing compliance checklist: FTC's CAN-SPAM guide covers: accurate header information, non-deceptive subject lines, ad identification where applicable, physical postal address requirement, and opt-out handling within 10 business days.

Online advertising disclosure checklist: FTC's internet advertising guide explains rules for online claims, disclosures, endorsements, children's advertising, and consumer protection issues. Disclosures must be clear and conspicuous — not buried in footnotes or hidden behind links.

Influencer and endorsement checklist: FTC endorsement guidance applies when using influencers, affiliates, testimonials, reviews, referral programs, or user-generated content. All material connections between the brand and the endorser must be clearly disclosed.

AI USE POLICY

AI use policy: If using AI tools in operations or products, document: allowed use cases, banned use cases, customer data restrictions, human review requirements, source verification requirements, disclosure rules, security controls, vendor review, and model-output quality standards. SBA has a free AI for Small Business guide. NIST's AI Risk Management Framework provides broader guidance. This policy is increasingly expected by customers, partners, and regulators."""}
        ]
    },

    # ── MARKETING & SALES DOCS ────────────────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What free documents should I create for marketing and sales?"},
            {"role": "assistant", "content": """Marketing and sales documentation converts strategy into repeatable revenue. These documents ensure every customer interaction is consistent, compliant, and tracked.

STRATEGY FOUNDATION

Marketing plan: SBA recommends a marketing plan to turn strategy into action, stay on budget, and persuade customers to buy. SCORE offers marketing plan templates. The plan covers target market, positioning, channels, budget, timeline, and success metrics.

Customer persona worksheet: Demographics, pain points, buying triggers, objections, budget, preferred channels, and alternatives for each key customer segment. Use SBA market research guidance and Census Business Builder to ground personas in real market data rather than assumptions.

SWOT analysis: Use SCORE's SWOT worksheet to identify strengths, weaknesses, opportunities, and threats and connect them to goals, strategy, and marketing approach. SWOT is most useful when paired with action — each quadrant should generate specific initiatives.

Brand guidelines: Logo usage, colors, fonts, tone, taglines, photo style, prohibited uses, trademark symbols if applicable, and approval workflow. Brand guidelines prevent inconsistency as more people create content for the company.

SALES PROCESS

Sales script: Opening, qualification questions, problem discovery, value proposition, proof/social proof, objection handling, close, follow-up procedure, and CRM notes. Scripts create consistency — every prospect gets the same quality of conversation regardless of which salesperson they talk to.

Lead tracker: Source, date, contact, industry, need, budget, stage, next action, quote sent, close probability, and deal value. A lead tracker is the minimum viable CRM for an early-stage business.

CRM pipeline template: Lead → Qualified → Discovery → Proposal → Negotiation → Won/Lost/Follow-up/Renewal. Pipeline visibility enables revenue forecasting and identifies where prospects are dropping out of the process.

CONTENT & CAMPAIGNS

Marketing calendar: Plan campaigns, content, email, ads, events, launches, seasonal pushes, review requests, referral campaigns, and performance reviews. A documented calendar prevents reactive marketing and enables systematic testing.

Content checklist: Topic, keyword, audience, call to action, compliance risks (FTC guidelines), image rights and copyright status, accessibility requirements, publish date, repurposing plan, and performance tracking.

Sales and marketing section of business plan: SCORE notes this section explains how you generate profit, create exposure, and sell the product. Required for most lender and investor conversations.

COMPLIANCE IN MARKETING

All marketing documents must account for FTC compliance requirements:
- Advertising claims must be truthful, not deceptive or unfair, and evidence-based
- Email campaigns must comply with CAN-SPAM (accurate headers, opt-out within 10 business days, physical address)
- Influencer and affiliate content requires clear disclosure of material connections
- Testimonials and reviews must reflect actual customer experiences
- Pricing claims must be accurate (no fake "compare at" prices)
- Guarantees must be honored as stated

The FTC can take action against businesses for deceptive marketing regardless of size. Marketing compliance is not optional — it is part of the foundational documentation."""}
        ]
    },

    # ── SCALING & EXPANSION DOCS ──────────────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What documents do I need when expanding or scaling a business?"},
            {"role": "assistant", "content": """Scaling documentation converts a working business into a system that can grow without proportionally increasing founder involvement. These documents are the infrastructure of scale.

GROWTH PLANNING

Established business plan: SCORE offers a business plan template specifically for established businesses planning growth, securing financing, or planning continued success. Different from a startup plan — assumes operational history and focuses on the next stage.

Growth strategy document: Define growth target, target customers, new channels, new products, pricing evolution, hiring plan, budget, risks, and key metrics. SBA's grow guide covers funding new growth, new locations, mergers and acquisitions, federal contracting, exporting, and special business groups.

Expansion financial forecast: Use a 3-year cash flow, P&L, and balance sheet projection to test expansion costs, expected revenue, break-even point, and capital needs. SCORE's financial projection templates cover these documents. Model multiple scenarios — conservative, base, and aggressive.

OPERATIONAL SCALING

New location checklist: SBA's expansion guidance says to update marketing, check finances, handle foreign qualification if the new location is a different state, and prepare for taxes and compliance requirements in the new location. Each state has its own registration, licensing, and tax requirements.

Hiring plan: New roles, timing, compensation, onboarding timeline, training requirements, management structure, and compliance requirements for each new hire. Scaling headcount without a hiring plan creates organizational chaos and culture drift.

Process delegation map: Identify tasks the owner must keep, tasks to delegate to employees, tasks to automate with software, and tasks to outsource to specialists. This map is the transition from founder-operated to management-operated.

PERFORMANCE MEASUREMENT

KPI dashboard: Track revenue, gross margin, net profit, cash, customer acquisition cost, conversion rate, average order value, retention rate, churn rate, utilization, inventory turnover, and customer satisfaction. Different metrics matter at different stages — define which KPIs drive your specific business model.

ACQUISITION & PARTNERSHIP

M&A checklist: SBA's merger/acquisition guide covers valuation, due diligence, funding, and preparing a merger or acquisition agreement. M&A requires specialized legal and financial counsel — the checklist is preparation, not a replacement for advisors.

Business valuation worksheet: Use before selling, buying, merging, raising capital, or bringing on partners. SBA's guidance emphasizes valuing the business before agreeing to a sale or merger. Common valuation methods: revenue multiple, EBITDA multiple, asset-based, and discounted cash flow.

Franchise evaluation checklist: If buying a franchise or expanding via franchise model, track fees, royalties, territory rights, support provided, training, restrictions, litigation history, unit economics of existing franchisees, and exit terms.

INTERNATIONAL EXPANSION

Export readiness checklist: Use International Trade Administration (ITA) export resources to assess product readiness, market demand, pricing, buyer strategy, logistics, payment risk, and export regulations.

Export plan: ITA's export plan guidance explains that a written strategic export plan should cover product/service selection, market research, pricing strategy, buyer strategy, and market entry planning. ITA's resources are free.

Export documents checklist: ITA provides resources on commonly used and special export documents — commercial invoices, bills of lading, packing lists, certificates of origin, inspections, and other country-specific requirements.

Trade finance checklist: ITA's Trade Finance Guide explains payment and financing options — letters of credit, documentary collections, open account, advance payment — and helps exporters evaluate payment risk and ensure they get paid."""}
        ]
    },

    # ── FUNDING DOCS ──────────────────────────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What documents do I need when seeking funding — loans, investors, or grants?"},
            {"role": "assistant", "content": """Funding documentation packages the business for external evaluation. Lenders, investors, and grant agencies each require a different set of documents, but there is significant overlap.

UNIVERSAL FOUNDATION

Funding plan: How much money is needed, why it's needed, how it will be used (use of funds), repayment plan or return expectation, owner contribution, collateral available, and projected return. This is the framing document for any funding conversation.

SBA funding guide: SBA's funding programs page covers options to start, grow, or recover after a declared disaster — including SBA-backed loans, SBA investment programs, and disaster assistance.

FOR LENDERS (DEBT FINANCING)

Lender package checklist: Business plan, personal financial statement, business financial statements (2-3 years if available), income tax returns (personal and business), bank statements (3-6 months), collateral documentation, debt schedule, licenses and permits, insurance certificates, and owner resume/biography.

SBA loan readiness checklist: SBA explains that SBA-backed loans reduce lender risk and can help small businesses get funding that might otherwise be unavailable. SBA does not lend directly in most cases — it guarantees loans made by approved lenders.

FOR INVESTORS (EQUITY FINANCING)

Pitch deck outline: Problem, solution, market size, traction, product, business model, go-to-market strategy, competitive landscape, team, financial projections, use of funds, and the ask. Investors see hundreds of decks — clarity, specificity, and honest traction data matter more than design.

Investor due diligence folder: Formation documents, cap table, customer contracts, financial statements, tax returns, IP documents (patents, trademarks, copyrights, assignments), employee and contractor agreements, compliance documentation, customer metrics, known legal issues, and product roadmap.

FOR GRANTS

Grant research tracker: Opportunity name, agency, eligibility requirements, application deadline, match requirement, allowable costs, prohibited costs, reporting requirements, and required application documents. Grants.gov notes that federal funding opportunities are generally for organizations supporting government-funded programs — not personal financial assistance.

SBIR/STTR checklist: If doing R&D, SBA's Small Business Innovation Research and Small Business Technology Transfer programs are highly competitive federal programs designed to encourage small businesses to explore technological potential and commercialization. Track eligibility, phase structure, agency focus areas, and commercialization requirements.

IMPORTANT WARNINGS

EIN and SAM.gov registration are always free. Never pay a third party to obtain an EIN from the IRS or to register on SAM.gov.

SBDC and SCORE counseling are free or low-cost. Use them before, during, and after funding conversations — many SBDC counselors have direct relationships with local lenders.

Grant fraud is common. Verify any grant opportunity against official government sources before paying any fee. Legitimate government grants do not require upfront payment.

Equity investment terms matter enormously. SAFE notes, convertible notes, preferred stock, liquidation preferences, anti-dilution provisions, pro-rata rights, and board seats all affect founder control and economics. Get qualified legal counsel before signing any investment documents."""}
        ]
    },

    # ── GOVERNMENT CONTRACTING DOCS ───────────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What documents do I need to start doing business with the federal government?"},
            {"role": "assistant", "content": """Federal contracting opens access to the U.S. government's roughly $700 billion annual procurement budget. These are the documents and registrations required to compete.

ELIGIBILITY & REGISTRATION

Federal contracting readiness checklist: SBA's contracting guide explains set-aside and sole-source contracts, basic eligibility requirements, how to win contracts, types of contracts, size standards for small business eligibility, prime and subcontracting rules, and governing regulations.

SAM.gov registration checklist: Use the official SAM.gov Entity Registration Checklist. This is the required step before bidding on federal contracts. SAM.gov states clearly: there is no charge to get a Unique Entity ID (UEI), register, or maintain entity registration. Never pay a third party to do this.

UEI (Unique Entity Identifier): The UEI replaced the DUNS number as the primary business identifier for federal contracting and grants. Obtained free through SAM.gov.

NAICS and size standard worksheet: Match products and services to the correct North American Industry Classification System (NAICS) codes. SBA size standards determine small business eligibility by NAICS code — size limits are set by either number of employees or average annual receipts. Getting NAICS codes right determines what set-aside contracts you qualify for.

MARKETING TO GOVERNMENT BUYERS

Capability statement: A one-page document for government contracting officers and prime contractors. Include: core competencies (what you do), differentiators (why you over competitors), past performance (relevant contracts completed), NAICS codes, certifications held, UEI/CAGE code, company contact information, and relevant company data (years in business, number of employees).

A capability statement is the government equivalent of a business card — every government-contracting small business should have one.

CERTIFICATIONS

Certification checklist: SBA's contracting assistance programs include certifications for businesses that qualify for contracts reserved for specific socio-economic categories:
- 8(a) Business Development Program (small disadvantaged businesses)
- HUBZone Program (businesses in historically underutilized business zones)
- Women-Owned Small Business (WOSB) and Economically Disadvantaged WOSB
- Service-Disabled Veteran-Owned Small Business (SDVOSB)
- Veteran-Owned Small Business (VOSB, through VA)

Each certification requires documentation of eligibility and application through the appropriate program. Certifications open access to set-aside contracts where only certified businesses can compete.

SUBCONTRACTING

Subcontracting tracker: SBA provides resources on prime and subcontracting, including subcontracting limitations and opportunities. Small businesses can enter federal contracting as subcontractors to prime contractors — often a lower-barrier entry point.

Subcontracting limitations restrict how much of the work in a small business set-aside contract can be subcontracted to large businesses. Violating these limitations is a serious compliance issue.

PRACTICAL STARTING SEQUENCE
1. Register on SAM.gov (free, required)
2. Identify your NAICS codes and size standard eligibility
3. Determine which certifications you qualify for
4. Build your capability statement
5. Research contracts on SAM.gov, USASpending.gov, and agency procurement forecast pages
6. Contact your local PTAC (Procurement Technical Assistance Center) — free government contracting assistance
7. Consider subcontracting with established prime contractors as a starting point

PTACs (Procurement Technical Assistance Centers) provide free or low-cost assistance to businesses pursuing government contracts — similar to SBDCs but specialized for contracting."""}
        ]
    },

    # ── EXIT & CLOSURE DOCS ───────────────────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What documents do I need when closing, selling, or transferring a business?"},
            {"role": "assistant", "content": """Exit documentation protects founders, employees, customers, and creditors during one of the highest-risk transitions in a business's lifecycle. These documents enable an organized, legal, and financially clean exit.

EXIT PLANNING

Business exit plan: Include desired exit date, target valuation, buyer profile, cleanup tasks required before sale, tax planning strategy, debt payoff plan, employee communication plan, customer communication plan, required legal documents, and owner transition plan. SBA provides free guidance for transferring ownership, selling, closing, and tying up loose ends.

Business valuation worksheet: Use before sale, merger, or partner buyout. SBA's M&A guidance emphasizes valuing the business before agreeing to a sale or merger. Methods include: revenue multiple (common for SaaS), EBITDA multiple (common for profitable businesses), asset-based valuation (common for asset-heavy businesses), and discounted cash flow (common for high-growth businesses).

CLOSING OBLIGATIONS

IRS closing a business checklist: IRS lists required steps including:
- Filing final federal, state, and local tax returns
- Filing final employment tax returns and issuing final W-2s
- Making final federal tax deposits
- Filing final 1099s for contractor payments
- Reporting the sale of business assets on Schedule D and Form 4797 if applicable
- Canceling the EIN and closing the IRS business account
- Keeping required records after closing

Record retention plan: IRS closing guidance requires keeping records after closure. Generally: income tax returns indefinitely; employment tax records at least 4 years; property records until the statute of limitations expires for the year of the property's sale; contracts typically 7 years.

ASSET & LIABILITY DOCUMENTATION

Asset list: Equipment, inventory, vehicles, domains, websites, software licenses, IP (patents, trademarks, copyrights), customer lists, licenses, permits, deposits, leases, and contracts. Buyers need a complete asset list for valuation and transfer.

Debt and obligation schedule: Loans, credit cards, leases, vendor balances, tax obligations, payroll liabilities, subscriptions, personal guarantees, and liens. Undisclosed liabilities create legal exposure after a sale.

Customer transfer plan: How customers will be notified, how service will continue, how contracts will be transferred or terminated, how prepayments will be handled, and how accounts will be closed or migrated. Customer handling during closure directly affects reputation and potential legal exposure.

SELLER PROTECTIONS

Representations and warranties: Statements the seller makes about the business's condition — accuracy of financials, no undisclosed liabilities, no pending litigation, IP ownership, contract status, employee matters. Inaccurate representations create post-closing legal liability.

Indemnification provisions: Define what the seller is responsible for if something goes wrong after the sale — and for how long (the indemnification survival period). Negotiate caps and floors on indemnification exposure.

Non-compete agreement: Common in business sales — restricts the seller from competing in the same market for a defined period. Enforceability varies by state. Understand what you're agreeing to before signing.

Earnout provisions: Payment structures where part of the purchase price depends on future performance. Earnouts are common but frequently disputed — define metrics precisely before agreeing to an earnout structure.

TAX CONSIDERATIONS AT EXIT

The tax treatment of a business sale depends on the deal structure (asset sale vs. stock sale), the type of assets sold, and how long assets were held. Asset sales typically produce a mix of ordinary income (for inventory, accounts receivable, depreciation recapture) and capital gains. Stock sales typically produce capital gains. This distinction can represent hundreds of thousands of dollars in tax difference — get qualified tax counsel before agreeing to deal structure."""}
        ]
    },

    # ── IRS RECORDKEEPING ─────────────────────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What does the IRS require for small business recordkeeping? How long do I need to keep records?"},
            {"role": "assistant", "content": """IRS Publication 583 (Starting a Business and Keeping Records) is the primary free resource. Here is what it requires and recommends.

WHY RECORDKEEPING MATTERS (IRS REASONING)

The IRS states that good records help you:
- Monitor the progress of your business
- Prepare financial statements
- Identify sources of income
- Keep track of deductible expenses
- Keep track of your basis in property
- Prepare your tax returns
- Support items reported on your tax returns during an IRS examination

In other words, records are not optional — they are the evidence that supports every number you report.

WHAT RECORDS TO KEEP

Gross income records: Receipts, invoices, cash register tapes, bank deposit slips, 1099 forms received, and records of barter or exchange.

Purchase records: Canceled checks, cash register tape receipts, credit card statements, and invoices. These document cost of goods sold and inventory.

Expense records: Canceled checks, cash register tapes, account statements, credit card statements, invoices, and petty cash slips for small cash payments. Document the business purpose of each expense.

Travel, transportation, entertainment, and gift expenses: These have stricter documentation requirements. IRS requires: amount, time and place, business purpose, and business relationship for each expense.

Assets records: Purchase price, date acquired, cost of improvements, section 179 deductions, deductions for depreciation, casualty losses, insurance reimbursements, and selling price. Keep these records until the statute of limitations expires for the year of the asset's disposal.

Employment records: IRS says to keep payroll tax records for at least 4 years after the due date of the tax or the date the tax was paid, whichever is later.

HOW LONG TO KEEP RECORDS (GENERAL RULES)

Income tax returns: Keep indefinitely.

Supporting documents for income tax returns: Keep until the statute of limitations expires — generally 3 years from the date you filed the return, or 2 years from the date the tax was paid, whichever is later. If you underreported income by more than 25%, the IRS has 6 years to assess additional tax.

Employment tax records: At least 4 years after the due date of the tax or payment date, whichever is later.

Property records: Keep until the statute of limitations expires for the year of the property's sale or disposal.

IRS Publication 334 (Tax Guide for Small Business) is the companion guide covering income and expenses for sole proprietors specifically — free from irs.gov.

RECORDKEEPING SYSTEMS

The IRS accepts both paper and electronic recordkeeping systems. Electronic records must accurately reproduce original records and be accessible to IRS personnel during an examination. A simple system: keep a consistent daily transaction log, store all receipts digitally (photograph immediately on receipt), reconcile with bank statements monthly, and back up all records to at least one offsite location.

The worst recordkeeping mistake is not having records at all. The second worst is having records but being unable to locate them during an examination. The solution to both is a consistent filing system maintained from day one."""}
        ]
    },

    # ── CYBERSECURITY PLAN ────────────────────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "How do I build a cybersecurity plan for a small business using NIST and CISA resources?"},
            {"role": "assistant", "content": """NIST's Small Business Cybersecurity Corner and CISA's Cyber Guidance for Small Businesses are both free and designed specifically for non-technical business owners. Here is how to use them to build a practical plan.

THE FIVE NIST CYBERSECURITY FRAMEWORK FUNCTIONS

IDENTIFY: Know what you have and what needs protecting.
- Create an inventory of all devices (computers, phones, tablets, servers, network equipment)
- Create an inventory of all software and cloud services
- Create a data inventory: what customer, employee, financial, and operational data you collect and where it lives
- Identify who has access to what

PROTECT: Put defenses in place.
- Accounts: Use strong unique passwords for every account. Use a password manager (Bitwarden, 1Password). Enable multi-factor authentication (MFA) on every account that supports it — especially email, banking, accounting, payroll, and domain registrar.
- Software: Keep all software and operating systems updated. Enable automatic updates. Uninstall software you don't use.
- Devices: Encrypt hard drives. Enable screen lock with short timeout. Have a policy for lost or stolen devices.
- Wi-Fi: Use WPA3 or WPA2 encryption. Separate guest network from business network. Use a VPN on public Wi-Fi.
- Backups: Follow the 3-2-1 rule — 3 copies of data, 2 different media types, 1 offsite. Test restoration quarterly.
- Training: Teach all employees to recognize phishing emails. CISA provides free phishing simulation resources.

DETECT: Know when something goes wrong.
- Enable logging on all critical systems
- Monitor accounts for unusual activity (most banks and services offer alerts)
- Use endpoint protection software on all devices

RESPOND: Have a plan for when an incident occurs.
- Incident response plan: who to call, what to shut down, how to preserve evidence
- Contact list: IT support, bank fraud line, cyber insurance carrier, legal counsel, and if customer data is affected, potentially state regulators
- Communication plan: what to tell customers if their data is affected

RECOVER: Get back to normal.
- Data restoration from verified backups
- Review of how the incident occurred and what failed
- Update of policies and controls to prevent recurrence

CISA-SPECIFIC SMALL BUSINESS RESOURCES

CISA's Cyber Guidance for Small Businesses provides role-based action plans — meaning different checklists for the owner, IT person, and general employees. CISA's key recommendations for small businesses:

1. Use multi-factor authentication — described as "the most impactful step" by CISA
2. Keep software updated — patches close the vulnerabilities attackers exploit
3. Think before you click — phishing is the most common initial attack vector
4. Use strong passwords and a password manager
5. Update/patch your software
6. Use a VPN when on public Wi-Fi
7. Back up data and ensure backups work

BUSINESS-SPECIFIC CYBERSECURITY DOCUMENTS TO CREATE

Cybersecurity policy: Acceptable use of company devices and accounts, prohibited activities, personal device rules, data handling requirements, and reporting procedures for suspected incidents.

Vendor security review checklist: Before sharing sensitive data with any vendor (payroll, accounting, CRM, email marketing, cloud storage), verify: they use encryption, they offer MFA, they have a breach notification process, and their contract includes data security provisions.

Incident response plan: Even simple — who is called first, what is shut down or disconnected, how evidence is preserved, when and how customers are notified, when law enforcement is involved, and who manages communications.

Access control and offboarding checklist: Every time someone leaves (employee, contractor, partner), revoke access to every system they had — email, accounting, payroll, website admin, social media, bank, CRM, cloud storage, domain, and any shared accounts. This is one of the most common and preventable security failures in small businesses."""}
        ]
    },

    # ── FTC ADVERTISING COMPLIANCE ────────────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What are the FTC rules that small businesses must follow for advertising, email marketing, and influencer promotions?"},
            {"role": "assistant", "content": """The FTC (Federal Trade Commission) enforces consumer protection laws that apply to every business regardless of size. Violations can result in civil penalties, injunctions, and reputational damage.

CORE ADVERTISING RULES

FTC's foundational rule: Advertising claims must be truthful, non-deceptive, and evidence-based.

Truthful: Claims cannot be false or mislead consumers about material facts. A material fact is something a consumer would consider important in their purchase decision.

Non-deceptive: An ad is deceptive if it creates a false impression in the mind of a reasonable consumer — even if every individual statement is technically true. The overall impression matters as much as the literal wording.

Evidence-based: Any objective claim about a product's performance must be supported by competent and reliable evidence before the claim is made. "Clinically proven," "9 out of 10 dentists recommend," and similar claims require actual data.

Comparison claims: If you claim your product is better than a competitor's, the comparison must be accurate, properly qualified, and defensible.

Pricing claims: "Compare at" prices, crossed-out prices, and "normally $X, now $Y" pricing must reflect genuine prior prices. Fake reference prices are a common FTC violation.

Guarantees and warranties: If you advertise a guarantee, you must honor it as advertised. The FTC's Magnuson-Moss Warranty Act requirements apply to written warranties on consumer products.

EMAIL MARKETING: CAN-SPAM RULES

Every commercial email must comply with the CAN-SPAM Act. Key requirements:

1. Accurate header information: The "From," "To," and routing information must identify the person or business that sent the message.
2. Non-deceptive subject lines: Subject lines cannot mislead recipients about the content of the message.
3. Identify commercial messages: Commercial emails must be identified as advertisements unless there is prior opt-in consent.
4. Include physical postal address: Every commercial email must include a valid physical postal address — a P.O. box is acceptable.
5. Honor opt-outs promptly: Opt-out requests must be honored within 10 business days. The opt-out mechanism must be simple and work for at least 30 days after the email is sent.
6. No selling opt-out lists: You cannot sell, lease, or transfer email addresses after someone has opted out.

CAN-SPAM applies to every commercial email, including business-to-business emails. Each separate email in violation can be subject to civil penalties.

INFLUENCER AND ENDORSEMENT RULES

The FTC's Endorsement Guides apply to any brand relationship with content creators, affiliates, ambassadors, or reviewers. Key requirements:

Material connections must be disclosed: Any connection between the brand and the endorser that might affect the credibility of the endorsement must be clearly disclosed. Material connections include: payment, free products, discounts, employment, family relationships, and close personal relationships.

Disclosures must be clear and conspicuous: "Clear" means the disclosure uses understandable language. "Conspicuous" means the disclosure is placed so consumers are likely to notice it. Hashtags like #ad, #sponsored, or #paid_partnership at the beginning of a post (not buried among other hashtags) are generally acceptable.

Testimonials must reflect genuine experiences: You cannot create fake testimonials, cherry-pick unrepresentative reviews, or use testimonials that no longer reflect typical results.

Typical results must be stated: If you show a testimonial with exceptional results (e.g., "I lost 50 pounds!"), you must clearly disclose what results consumers can typically expect.

ONLINE DISCLOSURES

Disclosures for online claims must be clear and conspicuous — not buried in footnotes, hidden behind links, or placed far below the fold. If a claim needs a disclosure to be non-deceptive, the disclosure must be unavoidable to the ordinary consumer reading the ad.

CHILDREN'S ADVERTISING

Additional rules apply to advertising directed at children, including COPPA (Children's Online Privacy Protection Act) requirements for websites directed at children under 13. FTC enforces COPPA.

PRACTICAL COMPLIANCE CHECKLIST

Before publishing any ad, landing page, or promotional content:
- Is every factual claim truthful and evidence-based?
- Does the overall impression accurately represent the product?
- Are comparison claims accurate and qualified?
- Are pricing claims based on genuine prior prices?
- Are guarantees honored exactly as stated?
- Are all material connections with influencers or affiliates disclosed?
- Do testimonials reflect genuine, typical experiences?
- If this is an email, does it meet CAN-SPAM requirements?
- Is there a functioning, easy opt-out mechanism?
- Are disclosures clear, conspicuous, and unavoidable?"""}
        ]
    },

    # ── BUSINESS DOCS FOLDER STRUCTURE ───────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What is the recommended folder structure for organizing all my business documents?"},
            {"role": "assistant", "content": """This is the complete business document folder structure for Google Drive, OneDrive, Dropbox, or local encrypted storage. Create these folders before you need them — retroactive organization is ten times harder than proactive organization.

RECOMMENDED FOLDER STRUCTURE

01 Business Plan
- Business idea validation worksheet
- Market research report
- Competitive analysis worksheet
- Business plan (startup or established)
- Lean startup one-page plan
- SWOT analysis

02 Formation and Ownership
- Business structure comparison document
- Formation documents (articles of incorporation, articles of organization, etc.)
- Operating agreement, bylaws, or partnership agreement
- Founder agreement
- Cap table (equity ownership tracking)
- Shareholder or membership agreements
- Annual meeting minutes if required

03 Licenses, Permits, and Tax IDs
- Business registration documents
- EIN confirmation letter
- State and local business licenses
- Industry-specific permits
- Zoning permits
- Sales tax registration
- License and permit renewal tracker
- Registered agent information

04 Banking and Funding
- Bank account documentation
- Funding plan
- Lender package
- Loan documents
- SBA documentation if applicable
- Grant applications and agreements
- Investor pitch deck
- Investment documents (SAFEs, term sheets, stock purchase agreements)
- Cap table (linked from 02)

05 Accounting and Taxes
- Chart of accounts
- Recordkeeping policy
- Monthly financial review worksheets (archived by month)
- Balance sheets (archived by period)
- Profit and loss statements (archived by period)
- Cash flow forecasts and actuals (archived by period)
- Tax returns (personal and business, all years — keep indefinitely)
- Tax payment receipts
- Annual report filings

06 Contracts and Legal
- Customer contracts and service agreements
- Vendor agreements
- Independent contractor agreements
- NDAs and confidentiality agreements
- Intellectual property assignments
- Lease agreements
- Loan agreements
- Purchase orders
- Amendments to any of the above
- Contract repository index

07 Customers and Sales
- Customer personas
- Lead tracker
- CRM pipeline export/backup
- Sales scripts
- Quote and proposal templates
- Invoice templates
- Customer support policy
- Refund and return policy

08 Marketing and Brand
- Brand guidelines
- Marketing plan
- Marketing calendar
- Content checklist
- Advertising compliance checklist
- Email marketing compliance checklist
- Influencer and endorsement checklist
- Campaign performance reports

09 Employees and Contractors
- Hiring checklist
- Job descriptions
- Offer letters (all current employees)
- Form I-9s (current and 3 years after termination for former employees)
- Payroll tax records
- Employee handbook (current version + all previous versions)
- Required workplace posters (copies or links)
- Performance reviews
- Disciplinary documentation
- Separation documentation
- Independent contractor agreements (linked from 06)

10 Vendors and Purchasing
- Vendor agreements (linked from 06)
- Vendor contact list
- Purchase orders
- Vendor performance notes

11 Insurance
- Insurance policy tracker
- All current insurance policies
- Certificates of insurance
- Claims history

12 Compliance
- Annual compliance calendar
- License renewal tracker
- Employment law compliance notes
- OSHA materials if applicable
- Anti-discrimination compliance notes
- Privacy policy (current and previous versions)
- AI use policy
- Data inventory

13 Cybersecurity and Data
- Cybersecurity plan
- Incident response plan
- Password and account recovery document (encrypted or in password manager — NOT plain text)
- Access control list
- Vendor security review notes
- Backup and disaster recovery plan

14 Operations and SOPs
- Operations manual
- Standard operating procedures (one file per process)
- Process delegation map
- KPI dashboard templates

15 Growth and Expansion
- Growth strategy document
- Expansion financial forecast
- New location checklist (if applicable)
- Hiring plan (growth-phase)
- M&A documentation if applicable
- Business valuation worksheet

16 Government Contracting
- SAM.gov registration documentation
- UEI/CAGE code record
- Capability statement
- NAICS and size standard worksheet
- Certification documentation
- Past performance references
- Subcontracting tracker

17 Exporting
- Export readiness checklist
- Export plan
- Export documents checklist
- Trade finance documentation

18 Disaster Recovery and Continuity
- Business continuity plan
- Business impact analysis
- Emergency contact sheet
- Backup and disaster recovery plan (linked from 13)
- SBA Business Resilience documentation

19 Exit, Sale, or Closure
- Business exit plan
- Business valuation worksheet (linked from 15)
- Asset list
- Debt and obligation schedule
- Customer transfer plan
- Record retention plan
- Closing legal documents

20 Archive
- All superseded versions of active documents
- Historical financial statements
- Closed contracts
- Former employee files (retained per IRS/legal requirements)

BEST PRACTICES
- Use consistent naming: YYYY-MM-DD_DocumentName_Version.ext
- Make folder 20 Archive the destination for everything outdated — never delete, archive
- Back up the entire structure to at least two locations (cloud + local encrypted)
- Review access permissions annually — limit access to what each person actually needs
- Store the password and account recovery document (folder 13) in an encrypted password manager, not in cloud storage accessible to everyone"""}
        ]
    },

    # ── STARTUP PRIORITIZED FIRST MOVES ──────────────────────────────────────
    {
        "messages": [
            {"role": "user", "content": "What should I do first when starting a business? Give me the prioritized sequence of documents and registrations."},
            {"role": "assistant", "content": """This is the prioritized sequence for moving from idea to legal, operating business. Do these in order — later steps depend on earlier ones.

PHASE 1 — VALIDATE BEFORE SPENDING (Days 1-7)

1. Business idea validation worksheet: Answer the core questions — problem, customer, solution, why now, willingness to pay, first test. Use Census Business Builder for market data. SBA's market research guidance for methodology.

2. Market research report: Validate that real demand exists for your specific solution, at a price that makes the business viable, in a market large enough to sustain you.

3. Competitive analysis worksheet: Confirm you understand the competitive landscape before committing to a direction.

4. Value proposition statement: "I help [specific customer] solve [specific problem] by providing [specific solution] so they can [specific outcome]." If you can't write this clearly, you're not ready to spend money.

PHASE 2 — PLAN THE FINANCES (Days 7-14)

5. Startup expenses worksheet (SCORE template): Estimate what it actually costs to start. Most founders dramatically underestimate. Include formation, equipment, inventory, technology, rent, marketing, licenses, insurance, payroll, professional services, and cash reserve.

6. 12-month cash flow statement: Model what money comes in and goes out each month. Identify when you run out of cash if revenue doesn't materialize. This determines how much funding you need.

7. Financial projections (SCORE template): Build the full picture — sales forecast, operating expenses, cash flow, income statement, balance sheet, break-even.

PHASE 3 — LEGAL FOUNDATION (Days 14-30)

8. Business structure decision: Compare sole proprietorship, LLC, corporation, and S corp. For most small businesses, LLC provides the best liability protection with simplest tax treatment. For venture-backed startups, Delaware C-Corp is standard. SBA and IRS both explain structure implications.

9. Business name search: State name search, trademark search (USPTO), domain availability, social media handle availability — in that order. Before registering anything.

10. State registration: Register your legal entity through your state's secretary of state or business registration office. Requirements and costs vary by state.

11. EIN application (IRS): Free, takes minutes, available immediately online at irs.gov. Apply after entity registration. Never pay a third party for an EIN.

12. License and permit research: Check federal, state, county, and city requirements for your specific industry and location. SBA and USA.gov both have license and permit finders.

13. Business bank account: Requires EIN, formation documents, and ownership documentation. Open this before accepting any business money — commingling personal and business funds undermines your liability protection.

PHASE 4 — OPERATIONAL FOUNDATION (Days 30-60)

14. Founder agreement (if multiple founders): Cover equity, vesting, IP ownership, roles, compensation, decision rights, founder exit, and deadlock resolution. Must happen before operations start — after is too late.

15. Operating agreement or bylaws: Documents ownership structure, voting rights, profit distribution, management, and dissolution procedures. Required for LLCs in many states; strongly recommended for all entities.

16. Insurance: At minimum — general liability, and workers' compensation if you have employees. SBDC or SCORE mentors can help identify coverage needs for your specific business type.

17. Operations manual and first SOPs: Document the core repeatable processes before you hire. You can only delegate what is documented.

18. Invoice and contract templates: Have these before your first customer transaction.

19. Privacy policy: Required before collecting any personal information through your website or app.

PHASE 5 — SALES AND GROWTH (Days 60+)

20. Marketing plan (SBA/SCORE guidance): Channel strategy, budget, timeline, and success metrics.

21. Customer personas and sales script: Based on actual customer interview data, not assumptions.

22. CRM or lead tracker: Even a spreadsheet is better than nothing. Track every prospect and every interaction.

23. KPI dashboard: Define which metrics matter for your specific business model and start tracking from day one.

ONGOING FROM DAY ONE

- Tax calendar: Set up quarterly estimated tax payment reminders immediately. Missing estimated tax payments triggers penalties.
- Recordkeeping system: Start the transaction log, receipt folder, and document organization on day one. Retroactive recordkeeping is significantly more difficult.
- Annual compliance calendar: Add all renewal dates as soon as you know them."""}
        ]
    },
]


def main():
    existing_keys = set()
    if OUT.exists():
        for line in OUT.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                msgs = obj.get("messages", [])
                if msgs:
                    key = msgs[0].get("content", "")[:80]
                    existing_keys.add(key)
            except Exception:
                pass

    added = 0
    with OUT.open("a", encoding="utf-8") as f:
        for pair in PAIRS:
            msgs = pair.get("messages", [])
            if not msgs:
                continue
            key = msgs[0].get("content", "")[:80]
            if key in existing_keys:
                continue
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")
            existing_keys.add(key)
            added += 1

    total = sum(1 for l in OUT.open(encoding="utf-8") if l.strip())
    print(f"Added {added} new pairs. Total: {total}")


if __name__ == "__main__":
    main()
