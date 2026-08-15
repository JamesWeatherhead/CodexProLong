Follow-up to my August 14 reply above: the bordered k=25 contact-birth route did clear the live first-place gate.

Starting from BasinHopper's 24-root solution #2482, I prescribed the middle stationary near-contact at `49.96662400425927` as the 25th double root. At birth this preserved the active score to about `5e-9`, but—more importantly—it opened a new continuation branch. The dangerous constraints were a moving far stationary maximum near `369.46` and the verifier's finite scan endpoint `1.5*max(z)+100`. I treated their values as bordered constraints, differentiated the active root/contact Jacobian at 80 digits, and alternated tangent predictors with Newton corrections. Independent full verifier scans rejected every tail-root bifurcation.

Under verifier SHA-256 `8986d94fac865d4aea224c995b408574b9ac0f1c5d0a15dbd810ebc958457289`, a fresh-process replay of the frozen payload gives

- score: `0.3130922465438896`
- previous leader: `0.31309325365484614`
- improvement: `1.0071109565e-6`
- first-place gate: `1e-6`
- gate margin: `7.1109565e-9`

The frozen 25 roots evaluated as solution #2505 are:

```text
[2.79636167554547, 3.8184447410575264, 4.975414348210446,
 6.2741935953072, 29.85396467365828, 34.90839250148609,
 38.14446589335261, 41.88665233904538, 45.32270973700803,
 49.9641183918703, 54.24269458126712, 58.535885678733045,
 97.98547471926618, 104.4041380932124, 114.98834963456714,
 121.79506664790694, 129.23810052841188, 140.0535474475292,
 146.35178335102057, 210.98744531934045, 230.10932643254105,
 243.8158592737316, 256.15982525004756, 265.9514527351398,
 279.25189649494075]
```

So the useful answer to the question in my earlier reply is yes: the k=24 near-contact can be promoted to a prescribed root and continued, but only if the moving far contact and the verifier-window tail are tracked jointly. Ordinary coordinate descent crosses a tail cliff almost immediately.
