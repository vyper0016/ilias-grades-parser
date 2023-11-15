
async function prepare_page(page_name) {
    var a_element = document.getElementById("redirect");
    a_element.onclick = ""
    await eel.prepare_page(page_name);
    window.location.href = page_name+".html";
}

function cooldown_links(){
    const links = document.getElementsByTagName("a");
    const link_redirects = [];
    for (let i = 0; i < links.length; i++) {
        link_redirects.push(links[i].onclick);
        links[i].onclick = null;
    }
    setTimeout(function(){
        for (let i = 0; i < links.length; i++) {
            links[i].onclick = link_redirects[i];
        }
    }, 500);
}