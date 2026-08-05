# First use and farm profile

GrowMaster seeds a small crop catalogue, six sample beds and three sample tasks so the interface can be evaluated immediately. During first administrator setup, the user names the farm and chooses whether to retain the sample beds and tasks. The default is a clean operational farm; the crop and variety catalogue remains available.

## Safe demo cleanup

Demo cleanup only runs when all of the following are true:

- the farm still has the original demo name,
- the original six beds are present and empty,
- the original three tasks are present and still planned,
- there are no plantings, harvests, costs, sales, orders, retail sales, crop plans, material usages or labor entries.

If any condition differs, GrowMaster treats the database as an existing installation and preserves every record. Farm naming and authentication setup still complete normally.

Once the farm has been named, later application restarts never recreate the sample beds or tasks. The crop catalogue is retained as reusable reference data.

## Consolidated profile

The **Nastavitve** screen manages one farm profile containing:

- farm and seller name,
- direct-sale invoice exemption,
- tax and registration numbers,
- seller address and IBAN,
- VAT note,
- business-premise and device codes,
- default invoice due period.

The farm name appears in the application header and is synchronized with direct-sale settings. New invoices copy the current profile into their immutable archive and PDF. Editing the profile never rewrites an already issued invoice or credit note.

The readiness indicator becomes green when a tax number and seller address are present. These fields are needed before issuing documents to business customers; consumer direct sales can continue under the configured agricultural exemption.
