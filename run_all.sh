rm last_run_status.txt

ls -c1 2008_2009/sessions/txt/*.txt | xargs -I {} python record_parser.py read {} {}.json --with-amendments
ls -c1 2009_2010/sessions/txt/*.txt | xargs -I {} python record_parser.py read {} {}.json --with-amendments
ls -c1 2011_2012/sessions/txt/*.txt | xargs -I {} python record_parser.py read {} {}.json --with-amendments

mv 2008_2009/sessions/txt/*.txt.json 2008_2009/sessions/json/
mv 2009_2010/sessions/txt/*.txt.json 2009_2010/sessions/json/
mv 2011_2012/sessions/txt/*.txt.json 2011_2012/sessions/json/
