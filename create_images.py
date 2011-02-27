#!/usr/bin/env python
# encoding: utf-8
import sys
import os
import mapnik
import pg
import fnmatch

# step 1.  Create file _stop_animation_cache from gtfs schema

db = 'cccta'
hst = 'localhost'
usr = 'gtfs'
agency = 'cht'
schema = 'gtfs'
con = pg.connect(dbname=db,host=hst,user=usr)

# step 1 create animation cache table if needed

try:
  con.query(" create temporary sequence id; \
  create table _stop_animation_cache as select nextval('id') as id, a._agency_id, a.arrival_time, \
  substring(arrival_time from E'^([^:]+):')::int * 60 * 60 + substring(arrival_time from E'^[^:]+:([^:]+):')::int * 60 + substring(arrival_time from E':([^:]+)$')::int as seconds_from_midnight, \
  substring(arrival_time from E'^([^:]+):')::int * 60 + substring(arrival_time from E'^[^:]+:([^:]+):')::int as minutes_from_midnight, \
  c.route_short_name, d.description, e.stop_name, e.stop_lat, e.stop_lon, \
  a._agency_id||d.description as color_code, \
  e.the_geom from stop_times a join trips b using (_agency_id,trip_id) join routes c using (_agency_id,route_id) join route_types d using (route_type) join stops e using (_agency_id,stop_id); \
  ")

  con.query("\
  CREATE INDEX _min_idx ON _stop_animation_cache USING btree (minutes_from_midnight);\
  CREATE INDEX _sec_idx ON _stop_animation_cache USING btree (seconds_from_midnight);\
  CREATE INDEX _time_idx ON _stop_animation_cache USING btree (arrival_time);\
  ALTER TABLE _stop_animation_cache ADD PRIMARY KEY (id);\
  ")
except pg.ProgrammingError:
  pass
  
#get extents
ext=con.query('select max(st_x(the_geom)),min(st_x(the_geom)),max(st_y(the_geom)),min(st_y(the_geom)) from _stop_animation_cache;').getresult()

# step 2 create shapefiles in ./shapefiles directory

os.system("rm -rf ../shapefiles/"+agency)
os.system("mkdir ../shapefiles/"+agency)
for i in con.query("select distinct minutes_from_midnight from _stop_animation_cache order by minutes_from_midnight;").getresult():
  try:
    con.query("drop table anim_tmp;")
  except pg.ProgrammingError:
    pass
  con.query("create table anim_tmp as select * from _stop_animation_cache where minutes_from_midnight = %s" % i[0])
  os.system("pgsql2shp -f ../shapefiles/%s/%s -u %s %s %s.anim_tmp" % (agency,i[0],usr,db,schema))
  
# step 3 use mapnik to make images in ./images directory.  Right now this has to be custom edited on a per-agency basis.

os.system('rm -rf ../images/'+agency)
os.system('mkdir ../images/'+agency)

# create a map

m = mapnik.Map(1000,1000,"+proj=latlong +datum=WGS84")
m.background = mapnik.Color('white')

# create a style
s = mapnik.Style()
# _base styles are for map of city
s_base = mapnik.Style()

# rules for style
r1=mapnik.Rule()
r2=mapnik.Rule()
r3=mapnik.Rule()

r_base=mapnik.Rule()
r_base.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#f2eff9')))
r_base.symbols.append(mapnik.LineSymbolizer(mapnik.Color('rgb(50%,50%,50%)'),0.1))

r1.filter = mapnik.Filter("[ROUTE_SHORT] = 'CL' or [ROUTE_SHOR] = 'S' or [ROUTE_SHOR] = 'J' or [ROUTE_SHOR] = 'T' or [ROUTE_SHOR] = 'SAT' or [ROUTE_SHOR] = 'V' or [ROUTE_SHOR] = 'CW' or [ROUTE_SHOR] = 'HS' or [ROUTE_SHOR] = 'N' or [ROUTE_SHOR] = 'NU'")
r2.filter = mapnik.Filter("[ROUTE_SHORT] = 'FCX' or [ROUTE_SHOR] = 'SFRJ' or [ROUTE_SHOR] = 'CCX' or [ROUTE_SHOR] = 'PX' or [ROUTE_SHOR] = 'U' or [ROUTE_SHOR] = 'JFX' or [ROUTE_SHOR] = 'CPX' or [ROUTE_SHOR] = 'D' or [ROUTE_SHOR] = 'F' or [ROUTE_SHOR] = 'G' or [ROUTE_SHOR] = 'FG' or [ROUTE_SHOR] = 'T' or [ROUTE_SHOR] = 'JN'")
r3.filter = mapnik.Filter("[ROUTE_SHORT] = 'SFRG' or [ROUTE_SHOR] = 'SFRT' or [ROUTE_SHOR] = 'NS' or [ROUTE_SHOR] = 'A' or [ROUTE_SHOR] = 'CM' or [ROUTE_SHOR] = 'RU' or [ROUTE_SHOR] = 'HU' or [ROUTE_SHOR] = 'DX' or [ROUTE_SHOR] = 'D' or [ROUTE_SHOR] = 'SAT'")

ps1 = mapnik.PointSymbolizer("./icons/circle-red.png","png",10,10)
ps1.allow_overlap = True
ps1.opacity = .75

ps2 = mapnik.PointSymbolizer("./icons/circle-green.png","png",10,10)
ps2.allow_overlap = True
ps2.opacity = .75

ps3 = mapnik.PointSymbolizer("./icons/circle-blue.png","png",10,10)
ps3.allow_overlap = True
ps3.opacity = .75

r1.symbols.append(ps1)
r2.symbols.append(ps2)
r3.symbols.append(ps3)


# append rules to transit style
s.rules.append(r1)
s.rules.append(r2)
s.rules.append(r3)

s_base.rules.append(r_base)
m.append_style('Base Counties',s_base)


# new layer
for i in os.listdir("../shapefiles/"+agency):
  if fnmatch.fnmatch(i,"*.shp"):
    
    f_in = "../shapefiles/"+agency+"/%s" % i
    f_out = "../images/"+agency+"/%04d.png" % int(i.split(".")[0])
    try:
      for i in os.listdir("../county_base/"+agency):
        if fnmatch.fnmatch(i,"*.shp"):
          base_lyr = mapnik.Layer('base',"+proj=latlong +datum=WGS84")
          base_lyr.datasource = mapnik.Shapefile(file="../county_base/%s/%s" % (agency,i))
          base_lyr.styles.append('Base Counties')
          m.layers.append(base_lyr)
      m.append_style('CHT',s)
      m.append_style('Base Counties',s_base)  
      lyr = mapnik.Layer('CHT',"+proj=latlong +datum=WGS84")
      lyr.datasource = mapnik.Shapefile(file=f_in) 
      lyr.styles.append('CHT')
      #lyr.title="%s" % i

      #print lyr.envelope()
      m.zoom_to_box(mapnik.Envelope(ext[0][0]-.001, ext[0][2]-.001, ext[0][1]+.001, ext[0][3]+.001))
      mapnik.render_to_file(m,f_out, 'png')
      m.remove_all()
    except RuntimeError:
      print "No shapefile %s." % f_in
      pass
  


