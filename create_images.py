#!/usr/bin/env python
# encoding: utf-8
import sys
import os
import mapnik
import pg

# step 1.  Create file _stop_animation_cache from gtfs schema

db = 'geo'
hst = 'localhost'
usr = 'gtfs'
agency = 'CTA'
schema = 'gtfs'
con = pg.connect(dbname=db,host=hst,user=usr)

# step 1 create animation cache table if needed

try:
  con.query(" create temporary sequence id; \
  create table _stop_animation_cache as select nextval('id') as id, a.agency_id, a.arrival_time, \
  substring(arrival_time from E'^([^:]+):')::int * 60 * 60 + substring(arrival_time from E'^[^:]+:([^:]+):')::int * 60 + substring(arrival_time from E':([^:]+)$')::int as seconds_from_midnight, \
  substring(arrival_time from E'^([^:]+):')::int * 60 + substring(arrival_time from E'^[^:]+:([^:]+):')::int as minutes_from_midnight, \
  c.route_short_name, d.description, e.stop_name, e.stop_lat, e.stop_lon, \
  a.agency_id||d.description as color_code, \
  e.the_geom from stop_times a join trips b using (agency_id,trip_id) join routes c using (agency_id,route_id) join route_types d using (route_type) join stops e using (agency_id,stop_id); \
  ")

  con.query("\
  CREATE INDEX _min_idx ON _stop_animation_cache USING btree (minutes_from_midnight);\
  CREATE INDEX _sec_idx ON _stop_animation_cache USING btree (seconds_from_midnight);\
  CREATE INDEX _time_idx ON _stop_animation_cache USING btree (arrival_time);\
  ALTER TABLE _stop_animation_cache ADD PRIMARY KEY (id);\
  ")
except pg.ProgrammingError:
  pass

# step 2 create shapefiles in ./shapefiles directory

minutes = con.query("select max(minutes_from_midnight) from _stop_animation_cache;").getresult()[0][0]
os.system("mkdir shapefiles")
for i in range(0,minutes):
  try:
    con.query("drop table anim_tmp;")
  except pg.ProgrammingError:
    pass
  con.query("create table anim_tmp as select * from _stop_animation_cache where minutes_from_midnight = %s" % i)
  os.system("pgsql2shp -f ./shapefiles/anim_%s -u %s %s %s.anim_tmp" % (i,usr,db,schema))
  
# step 3 use mapnik to make images in ./images directory.  Right now this has to be custom edited on a per-agency basis.

os.system('mkdir images')

# create a map

m = mapnik.Map(1000,1000,"+proj=latlong +datum=WGS84")
m.background = mapnik.Color('white')

# create a style
s = mapnik.Style()
s_base = mapnik.Style()

# rules for style

r_bart=mapnik.Rule()
r_muni_bus=mapnik.Rule()
r_muni_metro=mapnik.Rule()
r_muni_cc=mapnik.Rule()
r_caltrain=mapnik.Rule()

r_base=mapnik.Rule()
r_base.symbols.append(mapnik.PolygonSymbolizer(mapnik.Color('#f2eff9')))
#r.symbols.append(mapnik.LineSymbolizer(mapnik.Color('rgb(50%,50%,50%)'),0.1))

r_bart.filter = mapnik.Filter("[COLOR_CODE] = 'BARTsubway/metro'")
r_muni_bus.filter = mapnik.Filter("[COLOR_CODE] = 'SFMTAbus'")
r_muni_metro.filter = mapnik.Filter("[COLOR_CODE] = 'SFMTAstreetcar/light rail'")
r_muni_cc.filter = mapnik.Filter("[COLOR_CODE] = 'SFMTAcable car'")
r_caltrain.filter = mapnik.Filter("[COLOR_CODE] = 'Caltrainrail'")

ps_bart = mapnik.PointSymbolizer("./icons/circle-red.png","png",10,10)
ps_bart.allow_overlap = True
ps_bart.opacity = .75

ps_caltrain = mapnik.PointSymbolizer("./icons/circle-green.png","png",25,25)
ps_caltrain.allow_overlap = True
ps_caltrain.opacity = .75

ps_muni_bus = mapnik.PointSymbolizer("./icons/circle-blue.png","png",4,4)
ps_muni_bus.allow_overlap = True
ps_muni_bus.opacity = .2

ps_muni_metro = mapnik.PointSymbolizer("./icons/circle-blue.png","png",8,8)
ps_muni_metro.allow_overlap = True
ps_muni_metro.opacity = .2

ps_muni_cc = mapnik.PointSymbolizer("./icons/circle-blue.png","png",6,6)
ps_muni_cc.allow_overlap = True
ps_muni_cc.opacity = .2

r_bart.symbols.append(ps_bart)
r_caltrain.symbols.append(ps_caltrain)
r_muni_bus.symbols.append(ps_muni_bus)
r_muni_metro.symbols.append(ps_muni_metro)
r_muni_cc.symbols.append(ps_muni_cc)


# append rules to transit style
s.rules.append(r_bart)
s.rules.append(r_caltrain)
s.rules.append(r_muni_bus)
s.rules.append(r_muni_metro)
s.rules.append(r_muni_cc)

s_base.rules.append(r_base)

m.append_style('Base Counties',s_base)

base_lyr = mapnik.Layer('base',"+proj=latlong +datum=WGS84")
base_lyr.datasource = mapnik.Shapefile(file="./base_map/counties.shp")
base_lyr.styles.append('Base Counties')


# new layer
for i in range(1,minutes):
  
  f_in = "./shapefiles/anim_%s.shp" % i
  f_out = "./images/%04d.png" % i
  try:
    m.append_style('SF Metro',s)
    m.append_style('Base Counties',s_base)  
    lyr = mapnik.Layer('sf_muni',"+proj=latlong +datum=WGS84")
    lyr.datasource = mapnik.Shapefile(file=f_in) 
    lyr.styles.append('SF Metro')
    #lyr.title="%s" % i
    m.layers.append(base_lyr)
    m.layers.append(lyr)
    
    #print lyr.envelope()
    #Bay Area
    #m.zoom_to_box(mapnik.Envelope(-122.53867,37.003084,-121.567091,38.0189343386))
    #SF Only
    m.zoom_to_box(mapnik.Envelope(-122.53867,37.705764,-122.365447,37.836443))
    mapnik.render_to_file(m,f_out, 'png')
    m.remove_all()
  except RuntimeError:
    print "No shapefile %s." % f_in
    pass
  


