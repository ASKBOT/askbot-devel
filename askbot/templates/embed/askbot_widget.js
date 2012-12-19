var {{variable_name}} = {
  element_id: "{{variable_name}}",
  widgetToggle: function() {
    element = document.getElementById({{variable_name}}.element_id);
    element.style.visibility = (element.style.visibility == "visible") ? "hidden" : "visible";
    if (element.style.visibility == "visible"){
      $("#" + {{variable_name}}.element_id + " iframe").focus();
    }
  },
  toHtml: function() {
    var html = {{variable_name}}.createButton();
    var link = document.createElement('link');
    var protocol = document.location.protocol;

    link.setAttribute("rel", "stylesheet");
    link.setAttribute("href", protocol + '//{{host}}{%url render_ask_widget_css widget.id%}');

    //creating the div
    var motherDiv = document.createElement('div');
    motherDiv.setAttribute("id", {{variable_name}}.element_id);
    motherDiv.style.visibility = "hidden";

    var containerDiv = document.createElement('div');
    motherDiv.appendChild(containerDiv);

    {%if widget.outer_style %}
    outerStyle = document.createElement('style');
    outerStyle.innerText = "{{widget.outer_style}}";
    motherDiv.appendChild(outerStyle);
    {%endif%}

    var closeButton = document.createElement('a');
    closeButton.setAttribute('href', '#');
    closeButton.setAttribute('id', 'AskbotModalClose');
    closeButton.setAttribute('onClick', '{{variable_name}}.widgetToggle();');
    closeButton.innerHTML= 'Close';

    containerDiv.appendChild(closeButton);

    var iframe = document.createElement('iframe');
    iframe.setAttribute('src', protocol + '//{{host}}{% url ask_by_widget widget.id %}');

    containerDiv.appendChild(iframe);

    var body = document.getElementsByTagName('body')[0];
    if (body){
      body.appendChild(link);
      body.appendChild(motherDiv);
    }
  },
  createButton: function() {
    var label="{{widget.title}}"; //TODO: add to the model
    var buttonDiv = document.createElement('div');
    buttonDiv.setAttribute('id', "AskbotAskButton");

    var closeButton = document.createElement('input');
    closeButton.setAttribute('onClick', '{{variable_name}}.widgetToggle();');
    closeButton.setAttribute('type', 'button');
    closeButton.value = label;

    buttonDiv.appendChild(closeButton);
    
    return buttonDiv;
  }
};

previous_function = window.onload;
var onload_functions = function(){
  if (previous_function){
    previous_function();
  }
  {{variable_name}}.toHtml();
}

window.onload = onload_functions();
document.write({{variable_name}}.createButton().outerHTML);
