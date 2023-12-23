
const orgas = ["hhu-progra", "hhu-progra2"];
    
function pointsForExercise(exerciseName, username, token, orga) {
    const issueUrl = "https://api.github.com/repos/" + orga + "/" + exerciseName + "-" + username + "/issues/1"
    const headers = {
        "Authorization": "Token " + token
    };
    fetch(issueUrl, { headers }).then(response => {
        const tableElement = document.getElementById(exerciseName);
        if (!tableElement.innerText.includes("Ilias")) {
            tableElement.innerText = "N/A";
        }
        if (!response.ok) {
            console.warn(`status ${response.status} when fetching ${exerciseName}`);
            const nextOrga = orgas[orgas.indexOf(orga) + 1];
            if(nextOrga) {
                pointsForExercise(exerciseName, username, token, nextOrga);
            }
        } else {
            response.text().then(text => {
                const pointsStrings = text.split("Punkte: ")[1].split(" ")[0].split("/");
                const totalPoints = Number(pointsStrings[1].split("\\")[0]);
                const achievedPoints = Number(pointsStrings[0]);
                console.log(`${exerciseName} ${achievedPoints}`);

                const link = document.createElement("a");
                link.innerText = `${achievedPoints}/${totalPoints}`;
                link.href = issueUrl.replace("api.", "").replace("/repos", "");
                tableElement.innerHTML = "";
                tableElement.appendChild(link);

                addPoints(tableElement.parentElement.getElementsByClassName("total")[0], achievedPoints);

                const sheetNumber = Number(tableElement.parentElement.id.replace("blatt", ""));
                addPointsToSheet(sheetNumber, achievedPoints);
            });
        }
    });
}

function addPoints(element, points) {
    if(element.innerText == "") {
        element.innerText = points;
        return;
    }
    element.innerText = Number(element.innerText) + points;
}

function addPointsToSheet(sheetNumber, points) {
    document.querySelectorAll(`[id*=_${sheetNumber}_]`).forEach(e => addPoints(e, points));
}

function resetTotals() {
    Array.from(document.getElementsByClassName("total")).forEach(e => e.innerText = "");
}

function fetchPoints() {
    const token = document.getElementById("github_token").value;
    const username = document.getElementById("github_name").value;
    const sheetRows = document.getElementsByClassName("sheet");
    resetTotals();
    Array.from(sheetRows).forEach(row => {
        const dataCells = Array.from(row.getElementsByTagName("td")).filter(td => td.id !== "");
        dataCells.forEach(td => pointsForExercise(td.id, username, token, orgas[0]));
    });
}
