# How to Get ACTUAL 3D Secure Enrollment Data for BINs

## Research Report — March 2026

---

## 1. Visa Directory Server

### What It Is
Visa operates a Directory Server (DS) as part of the Visa Secure (formerly Verified by Visa) program. The DS is the authoritative source for which BIN ranges are enrolled in 3DS authentication. It stores card range data, maps BINs to their corresponding Access Control Server (ACS) URLs, and routes authentication requests between 3DS Servers and issuer ACS systems.

### Data Available
- **Card range data**: Start BIN / End BIN for enrolled ranges
- **Protocol versions supported**: Which versions of 3DS (2.1.0, 2.2.0, 2.3.1) the ACS supports for each range
- **ACS URL**: The endpoint for the issuer's Access Control Server
- **3DS Method URL**: URL for device fingerprinting (browser data collection)
- **DS Transaction ID**: Unique identifiers for routing

### How to Access
**You cannot access the Visa DS directly as an independent party.** Access requires:

1. **Be a licensed acquirer or payment facilitator** registered with Visa
2. **Operate an EMVCo-certified 3DS Server** — the 3DS Server is the ONLY component in the EMVCo architecture authorized to communicate with the Directory Server
3. **Obtain TLS certificates** from Visa for mutual authentication with the DS
4. **Pass EMVCo functional testing** — your 3DS Server must pass approval tests against the Visa DS
5. **Maintain PCI 3DS compliance** — your environment must be assessed against the PCI 3DS Core Security Standard

The 3DS Server communicates with the DS using the **Preparation Request (PReq)** message to download card range data, and the **Authentication Request (AReq)** to perform per-transaction enrollment checks.

### Cost / Requirements
- **EMVCo certification**: Fees per submission (detailed in 3DS Bulletin 001, not publicly priced — estimate $50K-$150K+ including lab testing)
- **PCI 3DS assessment**: $30K-$100K+ depending on environment complexity
- **Visa licensing/registration**: Requires existing acquirer relationship
- **Infrastructure**: Secure hosting environment meeting PCI 3DS Part 1 and Part 2 requirements
- **Ongoing**: Annual recertification, certificate renewal

### Reliability
**Authoritative — this IS the source of truth.** The DS is the canonical registry of 3DS enrollment. 100% accurate for Visa cards by definition. Card range data is refreshed via PReq at intervals (recommended hourly, minimum daily).

---

## 2. Mastercard Directory Server

### What It Is
Mastercard operates its DS for the Mastercard Identity Check (formerly SecureCode) program. Same architectural role as Visa's DS but with Mastercard-specific enrollment tooling.

### Data Available
- **Card range data**: Enrolled BIN ranges with start/end ranges
- **ACS URL mapping**: Which ACS handles authentication for each range
- **Protocol version support**: 3DS 2.1.0, 2.2.0, 2.3.1 capabilities per range
- **3DS Method URL**: For device data collection
- **DS public keys**: For message signing/encryption

### How to Access
Access follows a multi-step enrollment process:

1. **Register for Mastercard Identity Check** via Mastercard Connect portal
2. **Use the ISSM (Identity Solutions Services Management) tool** on Mastercard Connect to register specific BIN ranges that will participate in Identity Check
3. **Obtain TLS server/client certificates** via the Mastercard Key Management Portal for secure communication
4. **Obtain digital signing certificates** if applicable
5. **Complete production certificate connectivity** before merchant enrollment
6. **Operate an EMVCo-certified 3DS Server** — same requirement as Visa

**Critical detail**: BIN ranges enrolled for the old Mastercard SecureCode (3DS 1.0) do NOT automatically carry over. Separate enrollment is required for Identity Check (EMV 3DS / 3DS2).

### Cost / Requirements
- Same EMVCo certification and PCI 3DS requirements as Visa
- **Mastercard licensing fees**: Billed via MCBS Event ID 2VC8005 or 2VC8015, fees vary by region
- **Company registration**: Yields a Company ID (CID), Operator ID, billable ICA number, and 3DS Requestor ID prefix
- Must be an acquirer or authorized 3DS Requestor

### Reliability
**Authoritative — canonical source for Mastercard 3DS enrollment.** Same level of authority as Visa DS.

---

## 3. EMVCo 3DS Protocol — Who Can Query the DS?

### Architecture Overview
The EMVCo 3-D Secure Protocol Specification (v2.2.0 / v2.3.1) defines four domains:

| Domain | Components | Role |
|--------|-----------|------|
| **Acquirer** | 3DS Server, 3DS Requestor | Initiates authentication |
| **Interoperability** | Directory Server (DS), DS-CA | Routes messages between domains |
| **Issuer** | Access Control Server (ACS) | Authenticates cardholders |
| **Issuer** | 3DS SDK (mobile) | Client-side SDK for app-based auth |

### Who Can Query the DS?

**Only the 3DS Server can query the Directory Server.** This is a hard architectural constraint, not a policy choice:

- **PReq (Preparation Request)**: 3DS Server -> DS. Requests card range data. The DS responds with PRes containing all enrolled BIN ranges, supported protocol versions, ACS information, and 3DS Method URLs. This is the bulk data download mechanism.
- **AReq (Authentication Request)**: 3DS Server -> DS -> ACS. Per-transaction authentication request routed through the DS.

The 3DS Server must be:
1. **EMVCo-certified** (passed functional and security testing)
2. **Registered with each card scheme's DS** (Visa, MC, Amex, etc.)
3. **Operating in a PCI 3DS-compliant environment**
4. **Using mutual TLS authentication** with DS-issued certificates

### Card Range Cache Mechanism
The PReq/PRes flow is specifically designed for 3DS Servers to maintain a local cache of card range data:

- **Frequency**: Recommended once per hour, minimum once per 24 hours
- **Content**: Full set of enrolled card ranges with metadata
- **Purpose**: So the 3DS Server can instantly determine if a card is 3DS-enrolled without querying the DS per-transaction
- **This cache IS the "3DS enrollment database"** — it contains exactly what your platform needs

### The Catch
**You need to BE a 3DS Server operator (or work with one) to get this data.** There is no "read-only" or "lookup-only" access tier. The DS treats all connections as operational 3DS Server instances.

---

## 4. Payment Service Providers (PSPs) That Expose 3DS Data

### Adyen — BinLookup API (BEST OPTION)

**Endpoint**: `POST /get3dsAvailability` (BinLookup API v52/v54)

**What it returns**:
- Whether 3D Secure 2 is supported for the BIN
- DS public keys and DS identifier
- 3DS Method URL for device fingerprinting
- BIN start range and BIN end range
- Card brand information

**Access requirements**:
- Active Adyen merchant account
- API credentials (API key)
- The BinLookup API is separate from payment processing — you can query it without initiating a payment

**Cost**: Included with Adyen merchant account. No separate per-lookup fee documented. Adyen merchant accounts typically require a business entity and processing volume.

**Reliability**: HIGH — Adyen operates certified 3DS Servers connected to all major card scheme DSes. Their data comes directly from the DS card range cache. This is real data, not heuristics.

**Strategic assessment**: This is the most accessible path to real 3DS enrollment data. Adyen's BinLookup API effectively exposes their 3DS Server's card range cache via a simple REST API.

### Stripe — PaymentMethod `three_d_secure_usage.supported`

**What it returns**:
- `three_d_secure_usage.supported` — boolean field on the Card object within a PaymentMethod
- Indicates whether the card supports 3D Secure authentication

**Access requirements**:
- Active Stripe account
- Must create a PaymentMethod (tokenize a card) to see this field
- Available in the PaymentMethod retrieve and list API responses

**Limitations**:
- You must tokenize each card number to check — cannot do a pure BIN-level lookup
- The `supported` boolean is per-card, not per-BIN-range
- Stripe abstracts away the underlying DS data (no BIN ranges, no protocol versions)
- Rate limits and Terms of Service may restrict bulk lookups for non-payment purposes

**Cost**: Included with Stripe account (no per-lookup fee), but you need to tokenize cards.

**Reliability**: MEDIUM-HIGH — Stripe queries real DS data during tokenization, but the boolean is a simplified abstraction. You lose granularity.

### Mastercard Payment Gateway Services (MPGS) — Check 3DS Enrollment

**Endpoint**: `Check 3DS Enrollment` operation

**What it returns**:
- Enrollment status: `Y` (enrolled), `N` (not enrolled), `U` (unable to verify)
- Authentication scheme identifier
- Redirect URL for 3DS challenge flow

**Access requirements**:
- Active MPGS merchant account (through an MPGS-connected acquirer)
- Card number and expiry required as input
- Primarily designed for pre-payment enrollment verification

**Limitations**:
- Requires full card number, not just BIN
- Designed for transaction flow, not bulk BIN analysis
- Only covers Mastercard (and cards processed through MPGS)

**Cost**: Part of MPGS merchant account, processing fees apply.

**Reliability**: HIGH — Direct DS query for each check. Real-time enrollment status.

### Checkout.com — 3DS and BIN Data

**What it returns**:
- BIN lookup: issuer, card type, card category, issuer country
- 3DS enrollment status in payment flow responses (`enrolled: Y/N`)
- 3DS `downgraded` status

**Access requirements**:
- Active Checkout.com merchant account
- 3DS enrollment data comes during payment authentication, not as standalone lookup

**Limitations**:
- 3DS enrollment data is embedded in payment flow, not a standalone BIN lookup API
- BIN lookup gives issuer data but may not specifically flag 3DS support outside of payment context

**Cost**: Included with Checkout.com account.

**Reliability**: HIGH within payment flow; not designed for standalone BIN-level 3DS queries.

---

## 5. 3DS Server Vendors

### Netcetera 3DS Server

**Product**: Netcetera 3DS Server (SaaS and on-premise)

**Card Range Capabilities**:
- EMVCo-certified 3DS Server that maintains a card range cache from all connected DSes
- PReq/PRes mechanism downloads full card range data
- Admin UI for managing configurations
- Integration manual documents card range management

**Access to BIN Data**:
- If you are a Netcetera customer (acquirer/PSP using their 3DS Server), you could potentially access the card range cache through their APIs
- Their 3DS Server caches ranges per the EMVCo spec (hourly refresh)
- API endpoint for checking if a card supports 3DS2 before authentication

**Cost**: Enterprise pricing — typically $50K-$200K+ annually for SaaS, plus EMVCo certification if on-premise. Requires being an acquirer or PSP.

**Reliability**: AUTHORITATIVE — directly connected to scheme DSes.

### GPayments ActiveServer

**Product**: ActiveServer 3DS Server (SaaS)

**Card Range Capabilities**:
- **Explicitly caches BIN ranges** of cards enrolled in 3D Secure 2
- **API call available** to determine whether a given card supports 3DS2 *before* authentication
- RESTful API with JSON request/response format
- Documentation at docs.activeserver.cloud

**Access to BIN Data**:
- ActiveServer customers can query the cached BIN ranges
- The pre-authentication check is specifically designed for the use case of "does this card support 3DS?"
- Could potentially be used for BIN-level 3DS intelligence

**Cost**: Enterprise SaaS pricing, requires acquirer/PSP relationship.

**Reliability**: AUTHORITATIVE — same DS card range cache mechanism.

### Entersekt (acquired Modirum)

**Product**: 3DS ACS and 3DS Server solutions

**Capabilities**:
- Full EMVCo-certified 3DS stack (ACS + 3DS Server)
- Acquired Modirum in 2023, inheriting their 3DS Server (MPI Manager)
- Combined authentication platform

**Access**: Enterprise customers only. Primarily targets issuers (ACS) and acquirers (3DS Server).

**Cost**: Enterprise pricing, not publicly disclosed.

### Ravelin

**Product**: 3DS authentication service

**Capabilities**:
- Provides merchant enrollment for 3DS across multiple card schemes
- Partners with acquirers for DS connectivity
- Offers 3DS as a service without requiring merchants to operate their own 3DS Server

**Access**: Via Ravelin merchant account and API integration.

---

## 6. Card Scheme Programs — Published BIN Range Lists

### Visa Secure

**Does Visa publish a list of enrolled BIN ranges?**
**NO.** Visa does not publish a downloadable list of 3DS-enrolled BIN ranges. The enrollment data is:
- Stored in the Visa Directory Server
- Accessible only via PReq from certified 3DS Servers
- Updated continuously as issuers enroll/modify BIN ranges
- Considered proprietary/confidential card scheme data

### Mastercard Identity Check

**Does Mastercard publish a list of enrolled BIN ranges?**
**NO.** Same situation:
- Enrollment data managed via ISSM tool on Mastercard Connect
- Accessible only to registered acquirers/issuers
- Not published as a downloadable dataset
- BIN registration is per-issuer, managed through Mastercard's enrollment portal

### American Express SafeKey

Similar model — Amex operates its own DS and does not publish enrolled BIN ranges publicly.

### Why Schemes Don't Publish
- **Security**: Published BIN ranges could help fraudsters identify cards without 3DS protection
- **Dynamism**: Ranges change frequently as issuers enroll/update
- **Commercial**: The data is part of the scheme's value proposition to acquirers
- **Liability**: Public lists could create false assumptions about authentication requirements

---

## 7. Third-Party / Public Services

### 3dslookup.com

**What it claims**: Free BIN/IIN lookup service that shows whether a card supports 3D Secure.

**How it likely works**: Aggregation of historical transaction data, crowd-sourced data, and/or reverse-engineering from payment flow observations. NOT connected to actual Directory Servers.

**Available via**: Web interface and RapidAPI marketplace.

**Reliability**: LOW-MEDIUM — Not authoritative. Data may be stale, incomplete, or inaccurate. No guarantees on coverage or freshness. Useful for rough estimates but NOT suitable for a production intelligence platform.

### 3dsdb.com

Similar third-party aggregation service. Same reliability concerns.

### Basis Theory — Universal 3DS

**What it offers**: Enterprise 3DS service that abstracts multiple 3DS providers (Cardinal Commerce, Ravelin, 3DSecure.io, etc.). Not a standalone BIN lookup — it's a payment authentication router.

**Access**: Enterprise feature, contact sales. Not a BIN-level 3DS enrollment database.

### Cybersource BIN Lookup

**What it offers**: BIN lookup service returning issuer information, card type, etc. May include some 3DS-related data within the payment context.

**Access**: Requires Cybersource merchant account.

---

## 8. Feasibility Matrix

| Source | Data Quality | Access Difficulty | Cost | BIN-Level Query | Standalone Use |
|--------|-------------|-------------------|------|----------------|---------------|
| **Visa DS (direct)** | Authoritative | Extremely High | $200K+ setup | Yes (PReq) | No — requires 3DS Server |
| **MC DS (direct)** | Authoritative | Extremely High | $200K+ setup | Yes (PReq) | No — requires 3DS Server |
| **Adyen BinLookup** | High (from DS) | Medium | Merchant acct | Yes | YES — standalone API |
| **Stripe PM field** | Medium-High | Medium | Free with acct | Per-card only | Partial — must tokenize |
| **MPGS Check 3DS** | High (real-time) | Medium-High | Merchant acct | Per-card only | Within MPGS flow |
| **Checkout.com** | High | Medium | Merchant acct | In payment flow | No — payment context |
| **GPayments ActiveServer** | Authoritative | High | Enterprise $$ | Yes (cache API) | For customers only |
| **Netcetera 3DS Server** | Authoritative | High | Enterprise $$ | Yes (cache API) | For customers only |
| **3dslookup.com** | Low-Medium | Low (free/API) | Free/cheap | Yes | Yes — but unreliable |
| **Card scheme lists** | N/A | N/A | N/A | N/A | NOT PUBLISHED |

---

## 9. Strategic Recommendation for Bin-Intelligence

### Recommended Path: Adyen BinLookup API

**Why Adyen is the optimal choice:**

1. **Real DS data**: Adyen's `get3dsAvailability` endpoint queries their certified 3DS Server's card range cache, which is populated directly from Visa, Mastercard, and other scheme Directory Servers
2. **Standalone API**: Unlike most PSPs, Adyen's BinLookup is a separate API from payments — you can query 3DS availability without initiating a transaction
3. **Rich response**: Returns 3DS2 support boolean, DS public keys, BIN range start/end, and card brand — much more than a simple yes/no
4. **Accessible**: Requires a merchant account but no EMVCo certification, no PCI 3DS compliance, no scheme licensing
5. **Cost-effective**: Included with merchant account, no per-query fees documented

### Implementation Strategy

**Phase 1 — Adyen Integration (immediate)**:
- Obtain Adyen merchant account (test environment available)
- Integrate `POST /get3dsAvailability` from BinLookup API v54
- For each BIN in the database, query Adyen for real 3DS support data
- Replace heuristic `patch_status` with data-driven classification
- Cache results locally with daily refresh

**Phase 2 — Stripe Cross-Reference (validation)**:
- Use Stripe's `three_d_secure_usage.supported` as a secondary signal
- Cross-reference Adyen results for BINs where data differs
- Builds confidence in the data and catches edge cases

**Phase 3 — Consider 3DS Server Vendor Partnership (future)**:
- If the platform scales and needs the fullest possible data
- Partner with GPayments or Netcetera for direct card range cache access
- Requires significantly more investment but yields authoritative data

### Second-Order Effects to Consider

1. **Rate limiting**: Adyen may throttle bulk BIN lookups — implement respectful batching with delays
2. **Terms of Service**: Verify that Adyen's ToS permits BIN-level intelligence gathering vs. only pre-payment checks
3. **Data staleness**: Card range data changes as issuers enroll — schedule periodic re-queries
4. **Multi-scheme coverage**: Adyen covers Visa, Mastercard, Amex, and others — but verify coverage for smaller schemes (JCB, Discover, UnionPay)
5. **Regulatory**: Using payment infrastructure for intelligence gathering could raise questions — consult legal

---

## Sources

- [Adyen BinLookup API — get3dsAvailability](https://docs.adyen.com/api-explorer/BinLookup/54/post/get3dsAvailability)
- [Stripe PaymentMethod API — three_d_secure_usage](https://docs.stripe.com/api/payment_methods/retrieve)
- [Mastercard Identity Check Onboarding Guide](https://static.developer.mastercard.com/content/identity-check/uploads/files/mc_idc_onboard_guide_Acquirer.pdf)
- [Mastercard MPGS Check 3DS Enrollment](https://test-gateway.mastercard.com/api/documentation/apiDocumentation/rest-json/version/11/operation/3DS:%20%20Check%203DS%20Enrollment.html)
- [EMVCo 3DS Specification v2.2.0](https://docs.3dsecure.io/3dsv2/specification_220.html)
- [EMVCo 3DS Approval Processes](https://www.emvco.com/processes/emv-3-d-secure-approval-processes/)
- [Visa 3D Secure Developer Portal](https://developer.visa.com/pages/visa-3d-secure)
- [Netcetera 3DS Server Documentation](https://3dss.netcetera.com/3dsserver/doc/current/)
- [Netcetera 3DS Preparation (PReq/PRes)](https://3dss.netcetera.com/3dsserver/doc/2.11.0.1/3ds-preparation)
- [GPayments ActiveServer Documentation](https://docs.activeserver.cloud/en/)
- [Basis Theory 3D Secure](https://developers.basistheory.com/docs/features/3d-secure)
- [3dslookup.com](https://3dslookup.com/)
- [PCI 3DS Compliance — Schellman](https://www.schellman.com/services/pci-compliance/pci-3ds)
- [PCI 3DS Core Security Standard](https://blog.pcisecuritystandards.org/what-to-know-about-the-new-pci-3ds-core-security-standard)
- [Mastercard Identity Check Program Guide](https://static.developer.mastercard.com/content/identity-check/uploads/files/mastercardidentitycheckprogram.pdf)
- [Checkout.com 3D Secure Docs](https://www.checkout.com/docs/risk-management/3d-secure)
- [3D Secure Wikipedia](https://en.wikipedia.org/wiki/3-D_Secure)
- [Visa Discontinuation of 3DS 1.0 Notice](https://usa.visa.com/dam/VCOM/global/support-legal/documents/visa-will-discontinue-support-of-3d-secure.pdf)
- [n-software 3DS Server Component](https://cdn.nsoftware.com/help/TS2/cs/Server.htm)
- [Mastercard Identity Check — Corbado](https://www.corbado.com/blog/mastercard-identity-check)
