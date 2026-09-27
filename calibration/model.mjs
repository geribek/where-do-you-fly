export const rad = degrees => degrees * Math.PI / 180;
export function destination(lat, lon, km, bearing) {
  const a=rad(lat),b=rad(lon),d=km/6371,t=rad(bearing);
  const x=Math.asin(Math.sin(a)*Math.cos(d)+Math.cos(a)*Math.sin(d)*Math.cos(t));
  const y=b+Math.atan2(Math.sin(t)*Math.sin(d)*Math.cos(a),Math.cos(d)-Math.sin(a)*Math.sin(x));
  return {lat:x*180/Math.PI,lon:((y*180/Math.PI+540)%360)-180};
}
export function relative(observer,flight) {
  const a=rad(observer.latitude),b=rad(flight.lat),dl=rad(flight.lon-observer.longitude);
  const h=Math.sin((b-a)/2)**2+Math.cos(a)*Math.cos(b)*Math.sin(dl/2)**2;
  const km=6371*2*Math.asin(Math.min(1,Math.sqrt(h)));
  const bearing=(Math.atan2(Math.sin(dl)*Math.cos(b),Math.cos(a)*Math.sin(b)-Math.sin(a)*Math.cos(b)*Math.cos(dl))*180/Math.PI+360)%360;
  const compass=['N','NE','E','SE','S','SW','W','NW'][Math.round(bearing/45)%8];
  return {...flight,km,bearing,compass};
}
export function demoFlights(observer,airport,step=0) {
  return [[1.2,35,'inbound'],[3.8,110,'outbound'],[7.5,280,'inbound'],[12.4,205,'nearby'],[22,320,'inbound']].map(([km,bearing,kind],i)=>({
    id:`DEMO-${i+1}`,callsign:`DEMO ${i+1}`,kind,
    origin:kind==='outbound'?airport:'AAA',destination:kind==='inbound'?airport:'BBB',
    ...destination(observer.latitude,observer.longitude,Math.max(.6,km+Math.sin(step+i)*.4),bearing+step*3),
  }));
}
export function candidates(observer,flights,radius,onlyAirport=false) {
  return flights.map(f=>relative(observer,f)).filter(f=>f.km<=radius && (!onlyAirport||f.kind!=='nearby'))
    .sort((a,b)=>a.km-b.km||a.id.localeCompare(b.id));
}
export function recommendation(samples) {
  const seen=samples.filter(s=>s.seen),unseen=samples.filter(s=>!s.seen);
  if(!seen.length||!unseen.length) return {radius:null,conflict:false,message:'Mark at least one seen and one not seen to compare a radius.'};
  const ceiling=Math.min(...unseen.map(s=>s.km));
  const radius=Math.floor((ceiling-.1)*10)/10;
  if(radius<.5) return {radius:null,conflict:true,message:'An unseen sample is too close for a useful radius. Direction or obstructions may matter more.'};
  const dropped=seen.filter(s=>s.km>radius).length;
  return {radius,conflict:dropped>0,message:dropped
    ? `A ${radius.toFixed(1)} km radius excludes the unseen samples but also excludes ${dropped} seen sample(s). No circular radius fits all these observations.`
    : `Try ${radius.toFixed(1)} km: it includes your seen samples and excludes your not-seen samples. This small sample is not a visibility guarantee.`};
}
