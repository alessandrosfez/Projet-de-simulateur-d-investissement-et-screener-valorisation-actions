/* Rendus de cellule du tableau de criblage (AG Grid), chargés automatiquement par Dash depuis assets/
   et appelés par leur nom dans layout.stocks_column_defs (cellRenderer). */
var dagcomponentfuncs = (window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {});

/* Score composite (0-100) : le chiffre, puis une barre fine proportionnelle sur une piste pleine
   largeur, en vert à partir de 70, ambre de 40 à 70, rouge sous 40 (mêmes seuils que l'ancienne
   coloration de cellule). Le chiffre reste écrit : la couleur ne porte jamais seule le niveau. Un
   score manquant affiche « N/A » sans barre, jamais une barre vide qui se lirait comme 0. */
dagcomponentfuncs.ScoreBar = function (props) {
    var value = props.value;
    var h = React.createElement;
    if (value === null || value === undefined || isNaN(value)) {
        return h("span", { className: "score-na" }, "N/A");
    }
    var clamped = Math.max(0, Math.min(100, value));
    var tone = value >= 70 ? "good" : value >= 40 ? "warn" : "bad";
    return h("div", { className: "score-cell" },
        h("span", { className: "score-value" }, String(Math.round(value))),
        h("span", { className: "score-track", "aria-hidden": "true" },
            h("span", { className: "score-fill " + tone, style: { width: clamped + "%" } })));
};
