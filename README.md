# Minnesota Senate Journals
### Shining a little sunlight in the dark recesses of PDF documents

Minnesota Senate day journals are only available in PDF, which is rather
irritating when there are specific things you want read by a machine, but
are locked away in PDF.

The [Minnesota Senate website](http://senate.mn) is actually a great source
for data, however amongst the detailed records of bills and their status, 
there are no machine readable formats for who voted what, and when.

Thankfully, the Senate journals are quite consistent in terms of the language
used, however, getting the data out into the open is still a little bit of a
challenge.

## What is here?

Plaintext and JSON, and source URLs.

## JSON format

No firm decisions yet, but hopefully that will come soon.

## The future

 * Once vote parsing works out, include districts
 * consistent filename format


## Contributing

### Spot checking

It would be great to have additional people look at the output in the JSON
files, and compare this to what is available in PDF records, or the plaintext
versions. There are likely to be some parsing errors somewhere, that are very
worth squashing.

Data can be outputted with line numbers included in .json or .yaml files, so
that referring to the source document is possible. Would be fairly simple to
make an app to line these up, in order to aid checking, and also allow
submitting issues to github.

### Developing

The general process to converting a record is: 

 1.) run xpdf's `pdftotext -layout` on the file.
 2.) run the parser `python record_parser.py read FILENAME` (see the usage note
     for additional details.)

NB: Since I haven't made a for realz module out of the thing yet, use
`virtualenv` to set up an environment, and install the requirements `pip
install -r requirements.txt`, then activate, and you should be ready to develop
and parse.

If there are things that need fixing, open an issue or submit a pull request!

#### TODOs

##### 2009 - 2010 Senate Session

 * Include votes on amendments, resolutions
 * Bill committee memberships (if not already in machine-readable format on senate site)
 * Include mentions of certain keywords
   - any bills numbers mentioned
   - any committees?
 * ... What else is in these PDFs that isn't in a consistent machine readable format?

Also, search files within for TODO.


