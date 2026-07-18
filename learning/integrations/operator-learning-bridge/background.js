const API = "http://127.0.0.1:5000/api/learning/events";
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "OPERATOR_LESSON_COMPLETE") return;
  fetch(API, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(message.event)})
    .then(async response => ({ok:response.ok, body:await response.json()}))
    .then(result => {
      if (result.ok) chrome.notifications.create({type:"basic", iconUrl:"icon128.png", title:"Operator Zero", message:`${result.body.unit_title || "Lesson complete"}: +${result.body.xp || 0} XP`});
      sendResponse(result);
    }).catch(error => sendResponse({ok:false,error:String(error)}));
  return true;
});
