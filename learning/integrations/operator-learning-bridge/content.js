(() => {
  const SENT_KEY = "operatorZeroSentLessonsV11";
  let timer = null;
  let lastUrl = location.href;
  const text = el => (el?.textContent || "").replace(/\s+/g," ").trim();
  const routeParts = () => location.pathname.split("/").filter(Boolean);
  const lessonIdentity = () => {
    const heading = document.querySelector("h1, main h2, [data-testid*='lesson'] h1, [data-testid*='title']");
    return {url:location.href, title:text(heading) || document.title.replace(/\s*\|.*$/,"")};
  };
  const isVisible = el => !!el && el.getClientRects().length > 0;
  const correctSignal = () => [...document.querySelectorAll("main *")].some(el => {
    const t=text(el).toLowerCase();
    if (!isVisible(el) || t.length>80) return false;
    const semantic = el.getAttribute("role")==="alert" || /correct|success/i.test(el.className || "") || /correct|success/i.test(el.getAttribute("data-testid") || "");
    return semantic && /^(correct!?|answer correct|nice work!?|well done!?)$/.test(t);
  });
  const progressionSignal = () => [...document.querySelectorAll("button,a")].some(el => isVisible(el) && /^(continue|next|next lesson|complete lesson)$/i.test(text(el)) && !el.disabled);
  const selectedCorrectAnswer = () => [...document.querySelectorAll("[aria-checked='true'], input:checked")].some(el => {
    const row=el.closest("label,[role='radio'],[role='option'],li,button,div");
    return row && /correct|success|green/i.test(`${row.className} ${row.getAttribute("data-state")||""} ${row.getAttribute("data-testid")||""}`);
  });
  async function sentSet(){ return new Set((await chrome.storage.local.get(SENT_KEY))[SENT_KEY] || []); }
  async function markSent(id){ const s=await sentSet(); s.add(id); await chrome.storage.local.set({[SENT_KEY]:[...s].slice(-1000)}); }
  function buildEvent(identity){
    const parts=routeParts(); const nums=parts.map(p=>/^\d+$/.test(p)?Number(p):null).filter(v=>v!==null);
    const section=nums.at(-2)||0, unit=nums.at(-1)||0;
    const stable=(identity.url.split("?")[0] + "|" + identity.title).toLowerCase();
    return {event_id:`bootdev_${btoa(unescape(encodeURIComponent(stable))).replace(/[^a-z0-9]/gi,"").slice(0,70)}`, provider:"bootdev", resource_id:document.body.innerText.match(/learn\s+(python|linux|sql)/i)?.[0]?.toLowerCase().replace(/\s+/g,"_") || "bootdev_learn_linux", unit_id:identity.url.split("?")[0], url:identity.url.split("?")[0], title:identity.title, lesson_title:identity.title, section_number:section, unit_number:unit, verification:"bootdev_dom_v11"};
  }
  async function inspect(){
    if (location.href!==lastUrl){lastUrl=location.href;}
    const complete = correctSignal() && (progressionSignal() || selectedCorrectAnswer());
    if (!complete) return;
    const identity=lessonIdentity(), event=buildEvent(identity), sent=await sentSet();
    if (sent.has(event.event_id)) return;
    chrome.runtime.sendMessage({type:"OPERATOR_LESSON_COMPLETE",event}, async response => { if(response?.ok) await markSent(event.event_id); });
  }
  const observer=new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(inspect,450);});
  observer.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:["class","aria-checked","data-state","disabled"]});
  setInterval(inspect,2500); inspect();
})();
