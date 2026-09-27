import test from 'node:test';
import assert from 'node:assert/strict';
import {destination,relative,demoFlights,candidates,recommendation} from '../model.mjs';
const observer={latitude:0,longitude:0};
test('distance and bearing match a generated eastward target',()=>{
  const target=relative(observer,destination(0,0,10,90));
  assert.ok(Math.abs(target.km-10)<.00001);assert.ok(Math.abs(target.bearing-90)<.00001);assert.equal(target.compass,'E');
});
test('antimeridian distance uses the short route',()=>{
  const target=relative({latitude:0,longitude:179.9},{lat:0,lon:-179.9});assert.ok(target.km<23);assert.equal(target.compass,'E');
});
test('mock targets follow observer and chosen airport',()=>{
  const own={latitude:12.25,longitude:34.75};const fs=demoFlights(own,'ZZZ');
  assert.equal(fs.length,5);assert.equal(fs[0].destination,'ZZZ');assert.equal(fs[1].origin,'ZZZ');
  assert.ok(relative(own,fs[0]).km<2);
});
test('radius shrinking and airport-only filtering reduce the list',()=>{
  const fs=demoFlights(observer,'XXX');
  assert.equal(candidates(observer,fs,50).length,5);assert.equal(candidates(observer,fs,2).length,1);
  assert.equal(candidates(observer,fs,50,true).length,4);
});
test('suggestion requires both seen and unseen observations',()=>{
  assert.equal(recommendation([]).radius,null);assert.equal(recommendation([{km:2,seen:true}]).radius,null);
});
test('suggested radius separates compatible observations',()=>{
  const result=recommendation([{km:2,seen:true},{km:5,seen:false}]);assert.equal(result.radius,4.9);assert.equal(result.conflict,false);
});
test('far seen and near unseen observations expose radius limitation',()=>{
  const result=recommendation([{km:8,seen:true},{km:3,seen:false}]);assert.equal(result.conflict,true);assert.match(result.message,/No circular radius/);
});
test('unseen target very near observer cannot yield a usable cutoff',()=>{
  assert.equal(recommendation([{km:2,seen:true},{km:.3,seen:false}]).radius,null);
});
