# AmazonHelp Golden Set — Labeling Guidelines

Corpus: 178 AmazonHelp conversations (single-customer, >=3 turns, chronologically ordered).

Labels in `golden_set.csv` were produced by transparent rules and are a
**starting point for human review**. Correct them in `golden_set_review.csv`,
which is sorted least-confident first.

## Labeling procedure

1. Read `customer_message` first. Label the customer's **primary** goal.
2. Use `context` only to disambiguate; do not label the brand's reply.
3. If two intents fit, prefer the more specific one (the taxonomy is ordered).
4. `GENERAL_SERVICE_COMPLAINT` is a last resort, not a bucket for angry messages.
5. Tone never determines intent. Anger affects escalation, not intent.

## Intents

### DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED  (17 conversations)

**Definition.** Tracking or the brand claims the item was delivered, but the customer does not have it.

**Include.** Tracking says delivered/handed over/left in safe place; package stolen after delivery; signature the customer did not give.

**Exclude.** Item merely late with no delivery claim (use DELIVERY_LATE_OR_NOT_ARRIVED); complaints about the carrier in general with no specific undelivered order.

**Real examples from the dataset:**

- `AMZ-005` (conv 646): .@AmazonHelp Item has not been delivered but tracking says it was handed to me over an hour ago... 2nd time this has happened. Sort it out https://t.co/42W82GcARk
- `AMZ-025` (conv 2568): Hey @115821, why is your Prime 2-day delivery not arriving until Monday? Is there a holiday I don't know about?
- `AMZ-028` (conv 2586): @116324 not dlvd after 1 wk. U lied 2 @AmazonHelp saying left in safe place on Fri. Yesterday u said wld be dlvd 24-48hrs. Sort this now!

### DELIVERY_LATE_OR_NOT_ARRIVED  (33 conversations)

**Definition.** Order is late, delayed, not yet shipped, or has simply not arrived; no claim that it was delivered.

**Include.** Past the promised date; 'still hasn't shipped'; guaranteed/next-day delivery missed; delivery re-scheduled.

**Exclude.** Tracking claims delivery (use DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED); refund for a late order already requested (use REFUND_STATUS_OR_AMOUNT).

**Real examples from the dataset:**

- `AMZ-010` (conv 690): @115850 @115821 @AmazonHelp @115851 Order# 3632693-6196346. You couldn't deliver EVEN AFTER A MONTH. You should be ashamed of yourself.
- `AMZ-011` (conv 1695): @115821 my order hasn’t arrived (it was due 14th October). Can you help?
- `AMZ-020` (conv 1748): @AmazonHelp that is not my apartment!!!!!!! This is the sending time!!!! Where is my package!!!!!!!!!! https://t.co/EIY6DZUCDC

### ITEM_DAMAGED_WRONG_OR_COUNTERFEIT  (11 conversations)

**Definition.** The item arrived but is damaged, defective, the wrong item, or counterfeit.

**Include.** Damaged in transit or badly packed; dead on arrival; wrong size/model sent; fake or counterfeit goods.

**Exclude.** Item never arrived (delivery intents); customer only wants to start a return with no fault stated (use RETURN_OR_REPLACEMENT_REQUEST).

**Real examples from the dataset:**

- `AMZ-006` (conv 652): @AmazonHelp Is it possible to prevent AMZL from delivering my packages moving forward? Stuff is either lost/stolen/broken EVERY time.
- `AMZ-007` (conv 659): @115821, it’d be nice if the book I waited 4 months for wasn’t damaged inside of an undented box. #twinpeaks #twin… https://t.co/Lac4K7iQzJ https://t.co/JroqJKrH9Q
- `AMZ-017` (conv 1736): Two fake items in one day. Time to cancel my Amazon Prime membership. @AmazonHelp

### RETURN_OR_REPLACEMENT_REQUEST  (7 conversations)

**Definition.** Customer wants to return, replace, or exchange an item, or is blocked in the returns process.

**Include.** 'How do I return this'; return request failing; replacement scheduled but not collected; pickup not happening.

**Exclude.** Customer is chasing money already owed (use REFUND_STATUS_OR_AMOUNT); item fault is the main complaint (use ITEM_DAMAGED_WRONG_OR_COUNTERFEIT).

**Real examples from the dataset:**

- `AMZ-077` (conv 9812): @AmazonHelp Was sent this item in 6x9 size. Trying to return &amp; UPS did not show up today. I'd keep item if I could get refund for price difference. https://t.co/G1a6por32Z
- `AMZ-098` (conv 11572): Me ha tocado un inepto en @4496 keiere gestionar la recogida de mi pakete de @115821 se monta su ruta y yo como penelope a esperarle! 😤
- `AMZ-135` (conv 15279): @AmazonHelp 408-9273159-6369903.replacement ordered from 24th Oct.no1 contact me.Really worst courier service from Amazon

### REFUND_STATUS_OR_AMOUNT  (8 conversations)

**Definition.** A refund is owed, missing, delayed, or the wrong amount.

**Include.** 'Haven't received my refund'; refunded less than paid; refunded to gift card instead of card; refund promised but not issued.

**Exclude.** Customer is disputing a charge they never authorised (use UNEXPECTED_CHARGE_OR_BILLING_ERROR); return not yet started (use RETURN_OR_REPLACEMENT_REQUEST).

**Real examples from the dataset:**

- `AMZ-012` (conv 1699): @AmazonHelp I called customer service and was told my membership wouldn't be renewed. I was just charged today. How do I get a refund? https://t.co/SeoQUsA0VA
- `AMZ-024` (conv 2561): Erm @AmazonHelp I bought this item for £5.99... why am I only getting £1.67 back?! https://t.co/lb33bFOcW0
- `AMZ-026` (conv 2577): @115830 amazonuk took money without any https://t.co/w25zXi7DYp they are not giving it back nor giving clear statement of my refund proces

### UNEXPECTED_CHARGE_OR_BILLING_ERROR  (14 conversations)

**Definition.** Customer was charged unexpectedly or incorrectly, or a payment/pricing mechanism is behaving wrongly.

**Include.** Charged for a membership they cancelled; charged twice; price at checkout differs from listing; delivery fee wrongly applied; wallet/payment method failures.

**Exclude.** Customer wants money back from a return (use REFUND_STATUS_OR_AMOUNT); question is about what Prime costs or includes (use PRIME_MEMBERSHIP_OR_SUBSCRIPTION).

**Real examples from the dataset:**

- `AMZ-013` (conv 1708): @115821 being charged for amazon prime &amp; when I go to cancel it, it’s saying I’m not a member😠😠😠
- `AMZ-034` (conv 3737): @AmazonHelp Warum ist es mir (und scheinbar auch ein paar anderen) nicht möglich per Bankeinzug zu bezahlen?
- `AMZ-046` (conv 5147): なんかAmazon支払い方法変わりました？？

### PRIME_MEMBERSHIP_OR_SUBSCRIPTION  (12 conversations)

**Definition.** Questions about Prime or another subscription: value, benefits, cancelling, renewing, trials.

**Include.** How to cancel Prime; what Prime includes; trial converted to paid; membership benefits not honoured.

**Exclude.** The complaint is specifically an unexpected charge (use UNEXPECTED_CHARGE_OR_BILLING_ERROR); Prime is mentioned only as context for a late delivery (use the delivery intent).

**Real examples from the dataset:**

- `AMZ-003` (conv 624): @115825 also, beim Addams Family-Film in Prime sind Bild und Ton nicht wirklich synchron. Wie kommt's?
- `AMZ-016` (conv 1733): @116090 I signed up for Prime so I could preorder Battlefront II and get all the bonuses and now cust service is saying I won’t get bonus
- `AMZ-057` (conv 5782): @117086 tem previsao para liberar a terceira temporada de #mrrobot no #amazonprimebrasil ?

### ACCOUNT_ACCESS_OR_SECURITY  (10 conversations)

**Definition.** Customer cannot access their account, or the account's security/identity is in question.

**Include.** Password reset failing; account locked or blocked; 2-step code not arriving; email changed by someone else; unauthorised purchase attempts; account closure requests; household/sharing visibility.

**Exclude.** Payment instrument problems with normal access (use UNEXPECTED_CHARGE_OR_BILLING_ERROR).

**Real examples from the dataset:**

- `AMZ-004` (conv 643): Bought an @115821 Echo Show and it won’t recognize a single @AmazonHelp account in our household. WTF, guys?
- `AMZ-014` (conv 1713): @AmazonHelp if I add another adult to my Amazon household (with their own account) can they see my wishlists/photos/order history?
- `AMZ-027` (conv 2580): the @amazonhelp queue is clueless on Amazon Household

### DEVICE_OR_DIGITAL_SERVICE_ISSUE  (15 conversations)

**Definition.** A problem with an Amazon device or digital service rather than a physical order.

**Include.** Kindle, Echo/Alexa, Fire TV/Stick; Prime Video playback, buffering, missing episodes; the Amazon app or website misbehaving; accessibility features.

**Exclude.** The device arrived damaged (use ITEM_DAMAGED_WRONG_OR_COUNTERFEIT); the device simply hasn't been delivered (delivery intents).

**Real examples from the dataset:**

- `AMZ-001` (conv 272): amazonのfireTVstickが見れない😢
- `AMZ-018` (conv 1741): @115821 please spend time &amp; money to fix your app. Constant issues with it.
- `AMZ-019` (conv 1745): My Kindle not working properly is breaking my heart! 😩💔

### DELIVERY_EXPERIENCE_OR_CARRIER_COMPLAINT  (9 conversations)

**Definition.** Complaint about how delivery is carried out, or a request to change delivery handling; not about one missing order.

**Include.** AMZL/carrier quality complaints; rude or unsafe driver conduct; packages thrown or left in the rain; requests for delivery instructions or to avoid a carrier.

**Exclude.** One specific order is late or missing (delivery intents). If driver conduct is unsafe or criminal, still label here but escalation will fire on the hard trigger.

**Real examples from the dataset:**

- `AMZ-015` (conv 1718): I ordered some parts of my costume late, but my amazon has a map of the driver and they're like, 6 houses away.
- `AMZ-043` (conv 5125): I was just assaulted by an Amazon delivery person.
- `AMZ-059` (conv 5789): @115850 I have stopped ordering from your site, Amazon courier guys are very rude. I have given similar complaints to u no of tyms.

### GENERAL_SERVICE_COMPLAINT  (12 conversations)

**Definition.** Dissatisfaction with Amazon or its support overall, with no single recoverable transaction identified.

**Include.** 'Worst customer service'; repeated unanswered complaints; being hung up on; threats to leave or to take legal action, without a specific order to fix.

**Exclude.** Any message where a specific order, refund, charge, account, or device problem is identifiable — use that intent instead. This is the residual complaint bucket, not a catch-all for anger.

**Real examples from the dataset:**

- `AMZ-002` (conv 617): Way to drop the ball on customer service @115821 so pissed right now!
- `AMZ-023` (conv 2559): @AmazonHelp hello, I’m having an issue with a same day ship order. Can you help me?
- `AMZ-029` (conv 2602): Rapidly losing faith in @115821 and their #esl CS ability to solve problems. No resolutions or follow ups.

### OTHER_NON_ACTIONABLE  (30 conversations)

**Definition.** No support request: praise, jokes, third-party chatter, or scam/phishing warnings about fake Amazon messages.

**Include.** Positive feedback; humour; customers warning others about phishing SMS/email; unrelated mentions.

**Exclude.** Anything containing an actual request for help.

**Real examples from the dataset:**

- `AMZ-008` (conv 667): Anna Inspired in idea lab at school to be @115821 package being shipped to Narnia! "Amazon can go anywhere" according to Anna. https://t.co/TyvKhuu7su
- `AMZ-009` (conv 682): How @115821 packages china https://t.co/fO9vbus18E
- `AMZ-035` (conv 3745): @AmazonHelp infórmese... no voy a perder más mi tiempo...

## Escalation label

Grounded in observed AmazonHelp behaviour across this corpus: 81% of brand
replies contain a help/contact link, 59% apologise, 15% ask for a DM, 10%
mention phone. Amazon resolves *informational* questions in-thread and hands
off anything needing account access. The label mirrors that boundary — i.e.
what an agent without account access can actually finish.

### AUTO_HANDLE

The request can be satisfied with general policy, how-to, or public
information. No order lookup, no money movement, no identity check.
Examples: how to cancel Prime, how returns work, how to set delivery
instructions, device troubleshooting steps.

### ESCALATE

Fires if **any** of the following is true:

1. **Account or order lookup required** — the answer depends on this
   customer's specific order, refund, or account state.
2. **Money movement** — a refund, credit, replacement, or charge reversal
   must be decided or issued.
3. **Security or identity** — account takeover, unauthorised access or
   purchases, locked accounts, failed 2FA.
4. **Safety, legal, or criminal** — assault, theft, threats, legal action,
   consumer court, fraud allegations. This overrides everything else.
5. **Order identifier supplied** — the customer pasted an order number,
   which by definition makes the request account-specific.
6. **Churn risk / severe dissatisfaction** — explicit cancellation threats
   or strong profanity directed at the service.

Rules 4-6 override the intent's default. Rule 4 is absolute.

### Known edge cases to check by hand

- Multilingual messages (Japanese, German, Spanish, Portuguese, Hindi) —
  the keyword rules are English-biased and under-fire on these.
- Sarcasm and jokes that mention delivery ('shipped to Narnia').
- Scam/phishing warnings, which mention Amazon billing but ask for nothing.
- Messages that are pure anger plus an order number: intent is often the
  underlying order problem, not GENERAL_SERVICE_COMPLAINT.
